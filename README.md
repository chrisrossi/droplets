# droplets

`droplets` aids in the management of Digital Ocean (DO) droplets. `droplets` also has the
ability to act as an inventory script for an Ansible playbook.

## Using `droplets`

The basic command line usage allows you to build your own script to connect to your
DO environments. The script serve two purposes. First, the creation and
destruction of droplets based on defined blueprint. Second, is to act as an
Ansible invetory script for those droplets.

### Creating the script

Using `droplets` you will define your own script for your different DO deployments.
In your script you will define a `blueprint`.

#### Calling main

`main` requires a blueprint and also accepts some optional arguments.

 - `image` (default: ubuntu-14-04-x64)
 - `size` (default: 512mb)
 - `region` (default: nyc3)
 - `prefix` (default: '')
 - `api_token` (default: None)

The defaults will be used for every instance created unless you explicitly override
the arguments in your call to main or in the group definition of your blueprint.

`prefix` is useful when creating scripts for different DO envrionments. `prefix` will
be used when generating the names for the instances of your groups. For example if you
call `main` with `prefix=staging-` and you have an `app` group defined in your blueprint,
your instances will have the name `staging-app00`, `staging-app01`, etc...

#### Defining a blueprint

A blueprint is a standard python dictionary. A blueprint should contain a key entry for
every group. The value of each group should be another dictionary that will act
as a key/value store for hostvars that will be passed to an ansible playbook.

A group can contain some special keys which override the default values of `main`.

 - `size` (default: 512mb)
 - `image` (default: ubuntu-14-04-x64)
 - `region` (default: nyc3)
 - `n` (number of instances, default: 1)

Typical group names are things like _app_, _db_, and _loadbalancer_. The `droplet` script
will use your group name along with the `prefix` (see below) when creating instance names


#### API Token

You must also provide an API token. There are two ways to do this. First, you can pass
the `api_token` keyword argument to the `main` call. Second, you can set the environment
variable 'DIGITAL_OCEAN_TOKEN' to your token value. The later option is useful if you
intend to store your droplet script in a public repository.

#### Example

Here is a very simple example of a single application server and single database server blueprint.
They override none of the default values and the `app` group passes the hostvar `git_branch`
to the playbook.

```python
#!/usr/bin/env python

import sys
from droplets import main

blueprint = {
    'app': {
        'git_branch': 'master',
    },
    'db': {},
}

if __name__ == '__main__':
    main(blueprint, api_token='XXX', prefix='staging-')
```

### Running the script

Now with this staging script defined, we can issue commands on it directly. For
example

    ./staging --help

    Options:
        -h --help    Show this screen
        --list       Outputs inventory in json.
        --human      Outputs inventory in format suitable for human beings.
        --reconcile  Creates/deletes droplets as necessary to match blueprint.
        --hostkeys   Gets ssh host keys for hosts in inventory and install them in
                    ~/.ssh/known_hosts
        --destroy=<group>    Destroys the droplets in the specified group.

By default, the script will execute as if you have passed in the `--list` option. This allows the
droplets script to at as an inventory script for the ansible-playbook command.

If we wanted to create these instances to prepare for a playbook run we would use the `--reconcile` option. It is
worth mentioning that `--reconcile` will not retroactively reconcile changes to `size`, `image`, or `region`.
You will need to login to DO to make adjustments to size OR use `--destroy` on the group and then `--reconsile`.

### Running with ansible-playbook

Now that you have your DO instances deployed how you want (using `--reconcile`). You can use your droplets script
as an inventory script for your playbook.

    ansible-playbook -i staging deploy-staging.yaml

