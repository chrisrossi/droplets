# droplets

`droplets` aids in the management of Digital Ocean (DO) droplets. It also has the
ability to act as an inventory script for an Ansible playbook.

## Using `droplets`

The basic command line usage allows you to build your own script to connect to your
DO environments. These scripts serve two purposes, the first is the creation and
repeaing of droplets based on your define blueprint, the second is to act as an
Ansible invetory script for those droplets.

### Creating the script

Using `droplets` you'll define your own script for your different DO deployments.
In your script you will define an `api_token` and `blueprint`.

You must provide a value for `api_token`, if you supply None, you must set the
`DIGITAL_OCEAN_TOKEN` environment variable to the token value or else a LookupError
exception will be raised. Using the environment variable is useful if you intend
to store your droplets script in a public repository.

`blueprint` is a standard python dictionary. It should contain a key entry for
every group. The value of each group should be another dictionary that will act
as a key/value store for hostvars that will be passed to an ansible playbook.
The group dictionary has one special key, `n`, which will determine the number of
instances a group will have (default: 1).

Below is an example of a script for a staging environment.

```python
#!/usr/bin/env python

import sys
from droplets import main

# Set in DIGITAL_OCEAN_TOKEN environment variable.
api_token = None

blueprint = {
    'staging-group': {
        'n': 5,
        'copyprod': False,
        'git-branch': 'staging',
    }
}

if __name__ == '__main__':
    main(api_token, blueprint)
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

### Running with ansible-playbook

Now that you have your DO instances deployed how you want (using `--reconcile`). You can use your droplets script
as an inventory script for your playbook.

    ansible-playbook -i staging deploy-staging.yaml

