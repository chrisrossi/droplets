"""
Retrieves inventory to use for Ansible from Digital Ocean.  Can automatically
create any necessary droplets or block storage volumes.
"""
import json
import os
import re
import requests
import subprocess
import sys
import time

from docopt import docopt

__version__ = '1.0dev'


usage = """
Digital Ocean server inventory

Usage:
    {0} --reconcile
    {0} --human
    {0} --list
    {0} --hostkeys
    {0} --destroy=<group>
    {0} --images

Options:
    -h --help    Show this screen
    --list       Outputs inventory in json.
    --human      Outputs inventory in format suitable for human beings.
    --reconcile  Creates/deletes droplets as necessary to match blueprint.
    --hostkeys   Gets ssh host keys for hosts in inventory and install them in
                 ~/.ssh/known_hosts
    --destroy=<group>    Destroys the droplets in the specified group.
    --images     Show available Digital Ocean images.
""".format(sys.argv[0])


def main(blueprint,
         image='ubuntu-16-04-x64',
         size='512mb',
         region='nyc3',
         prefix='',
         api_token=None,):
    args = docopt(usage)

    if api_token is None:
        api_token = api_token_from_env()

    api = DigitalOceanInventory(
        api_token, blueprint,
        image=image,
        size=size,
        region=region,
        prefix=prefix)

    if args['--hostkeys']:
        install_hostkeys(api)
    elif args['--destroy']:
        destroy_droplets(api, args['--destroy'])
    elif args['--images']:
        for image in api.get_images():
            if image['slug']:
                print(image['slug'])
    else:
        if args['--reconcile']:
            api.reconcile()
        if args['--reconcile'] or args['--human']:
            for name, vars in api.inventory.items():
                if 'hosts' in vars:
                    print('%s: %s' % (name, ' '.join(vars['hosts'])))
        else:
            print(json.dumps(api.inventory, indent=4))


def first_with(seq, cond):
    """
    Returns first item in seq which satisfies cond, or returns None.
    """
    for i in seq:
        if cond(i):
            return i


def get_in(mapping, *path):
    """
    Traverses a tree of dictionaries to get node specified by path, or returns
    None.
    """
    obj = mapping
    while obj and path:
        name, path = path[0], path[1:]
        obj = obj.get(name)
    return obj


def reconciled(blueprint, inventory):
    hostvars = inventory['_meta']['hostvars'].values()
    droplets = (h['droplet'] for h in hostvars)
    for droplet in droplets:
        if droplet['status'] != 'active':
            return False

    for name, vars in blueprint.items():
        if vars.get('n', 1) != len(inventory[name]['hosts']):
            return False

    return True


def api_token_from_env():
    do_token = 'DIGITAL_OCEAN_TOKEN'
    if do_token in os.environ:
        return os.environ[do_token]
    else:
        raise LookupError(
            '(required) %s environment variable not found.' % (do_token))


class DigitalOceanInventory(object):
    _volumes = None

    @property
    def inventory(self):
        inventory = getattr(self, '.inventory', None)
        if not inventory:
            inventory = self._get_inventory()
            setattr(self, '.inventory', inventory)
        return inventory

    def __init__(self, token, blueprint,
                 image='ubuntu-16-04-x64',
                 size='512mb',
                 region='nyc3',
                 prefix=''):
        self.token = token
        self.blueprint = blueprint
        self.image = image
        self.size = size
        self.region = region
        self.prefix = prefix

        self.ssh_key = self.get_or_install_ssh_key()
        self.host_pattern = re.compile('%s[a-z]+\d\d' % self.prefix)

    def reconcile(self):
        inventory = self._get_inventory(create=True)
        self.remove_extra_droplets()
        while not reconciled(self.blueprint, inventory):
            time.sleep(10)
            inventory = self._get_inventory()
        setattr(self, '.inventory', inventory)

    def api_call(self, method, path, data=None):
        while True:
            headers = {'authorization': 'Bearer %s' % self.token}
            if path.startswith('http:'):
                path = 'https:' + path[5:]
            if path.startswith('https'):
                url = path
            else:
                url = 'https://api.digitalocean.com/v2' + path
            if data and not isinstance(data, dict):
                headers['content-type'] = 'application/json'
            response = method(url, headers=headers, data=data)
            if response.status_code == 422:
                # We tried to do something to a droplet that's not ready yet
                # Wait a few seconds then try again
                print("Waiting on droplet")
                time.sleep(4)
                continue
            if response.status_code not in (200, 201, 202, 204):
                raise Exception(
                    "Unexpected response from Digital Ocean API: %d: %s" % (
                        response.status_code, response.text))
            return response

    def get_all(self, path, key):
        response = self.api_call(requests.get, path).json()
        objects = response[key]
        next_url = get_in(response, 'links', 'pages', 'next')
        while next_url:
            response = self.api_call(requests.get, next_url).json()
            objects.extend(response[key])
            next_url = get_in(response, 'links', 'pages', 'next')

        return objects

    def get_ssh_keys(self):
        return self.get_all('/account/keys', 'ssh_keys')

    def create_ssh_key(self, name, keyfile):
        response = self.api_call(requests.post, '/account/keys', data={
            'name': name,
            'public_key': keyfile
        }).json()
        return response['ssh_key']

    def get_images(self):
        return self.get_all('/images', 'images')

    def get_regions(self):
        return self.get_all('/regions', 'regions')

    def get_droplets(self):
        return self.get_all('/droplets', 'droplets')

    def create_droplet(self, name, vars):
        print("Create droplet {}".format(name))
        slug = vars.get('image', self.image)
        size = vars.get('size', self.size)
        region = vars.get('region', self.region)
        images = self.get_images()
        for image in images:
            if image['slug'] == slug:
                break
        else:
            raise Exception("Can't find image.")

        parameters = {
            'name': name,
            'region': region,
            'size': size,
            'image': image['id'],
            'ssh_keys': [self.ssh_key['id']],
        }
        response = self.api_call(requests.post, '/droplets',
                                 data=json.dumps(parameters)).json()
        return response['droplet']

    def destroy_droplet(self, droplet):
        print('destroy droplet {}'.format(droplet['name']))
        self.api_call(requests.delete, '/droplets/%d' % droplet['id'])

    def get_or_install_ssh_key(self):
        """
        Will make sure that current user's public ssh key is uploaded to
        Digital Ocean.  Installs the key if it is not already there.  Assumes
        the user's key is stored locally at `~/.ssh/id_rsa.pub`.  Returns the
        name of the ssh key as it is known to Digital Ocean.  This will be the
        key installed on any droplets created by this script.
        """
        keyfile = open(os.path.expanduser('~/.ssh/id_rsa.pub')).read()
        name = keyfile.rsplit(None, 1)[1]
        key = first_with(self.get_ssh_keys(), lambda x: x['name'] == name)
        if not key:
            key = self.create_ssh_key(name, keyfile)
        return key

    def get_volumes(self):
        if self._volumes is None:
            self._volumes = self.get_all('/volumes', 'volumes')
        return self._volumes

    def create_volume(self, name, size, region):
        print("Creating volume {}".format(name))
        parameters = {
            'name': name,
            'region': region,
            'size_gigabytes': size,
        }
        data = json.dumps(parameters)
        response = self.api_call(requests.post, '/volumes', data=data)
        return response.json()['volume']

    def attach_volume(self, droplet, volume):
        print("Attaching volume {} to droplet {}".format(
            volume['name'], droplet['name']))
        parameters = {
            'type': 'attach',
            'droplet_id': droplet['id'],
        }
        data = json.dumps(parameters)
        path = '/volumes/{}/actions'.format(volume['id'])
        self.api_call(requests.post, path, data=data)

    def _get_inventory(self, create=False):
        inventory = {}
        hostvars = {}
        droplets = self.get_droplets()
        for groupname, vars in self.blueprint.copy().items():
            hosts = []
            vars = vars.copy()
            n = vars.pop('n', 1)
            for i in range(n):
                hostname = '%s%s%02d' % (self.prefix, groupname, i)
                droplet = first_with(droplets, lambda x: x['name'] == hostname)
                if not droplet:
                    if not create:
                        continue
                    droplet = self.create_droplet(hostname, vars)

                droplet_volumes = vars.get('volumes')
                if droplet_volumes:
                    existing = self.get_volumes()
                    for name, voldata in droplet_volumes.items():
                        id = self.prefix + name
                        voldata['id'] = id
                        volume = first_with(
                            existing, lambda x: x['name'] == id)

                        if not volume:
                            if not create:
                                continue
                            region = voldata.get('region', vars.get(
                                'region', self.region))
                            size = voldata['size']
                            volume = self.create_volume(id, size, region)
                            self._volumes = None

                        if (create and (not volume['droplet_ids'] or
                                volume['droplet_ids'][0] != droplet['id'])):
                            self.attach_volume(droplet, volume)

                networks = get_in(droplet, 'networks', 'v4')
                for network in networks:
                    if network["type"] == "public":
                        host = network['ip_address']
                        hosts.append(host)
                        hostvars[host] = {'droplet': droplet}
                        break

            inventory[groupname] = {'hosts': hosts, 'vars': vars}

        inventory['_meta'] = {'hostvars': hostvars}
        inventory['all'] = {'vars': {'do_api_token': self.token}}
        return inventory

    def remove_extra_droplets(self):
        for droplet in self.get_droplets():
            hostname = droplet['name']
            if not self.host_pattern.match(hostname):
                continue
            group, i = hostname[len(self.prefix):-2], int(hostname[-2:])
            if group in self.blueprint:
                n = self.blueprint[group].get('n', 1)
                if i >= n:
                    self.destroy_droplet(droplet)


def install_hostkeys(api):
    for group in api.inventory.values():
        for host in group.get('hosts', ()):
            subprocess.check_call('ssh-keygen -f ~/.ssh/known_hosts -R %s' %
                                  host, shell=True)
            subprocess.check_call('ssh-keyscan %s >> ~/.ssh/known_hosts' %
                                  host, shell=True)


def destroy_droplets(api, group):
    inventory = api.inventory
    for host in hosts_from(inventory, group):
        droplet = get_in(inventory, '_meta', 'hostvars', host, 'droplet')
        api.destroy_droplet(droplet)


def hosts_from(inventory, group='all'):
    for name, vars in inventory.items():
        if name == group or group == 'all':
            for host in vars.get('hosts', ()):
                yield host
