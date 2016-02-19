import pytest
import os

from droplets import api_token_from_env


def test_api_token_from_env():
    os.environ['DIGITAL_OCEAN_TOKEN'] = 'testtoken'
    assert api_token_from_env() == 'testtoken'


def test_api_token_from_env_nil():
    with pytest.raises(LookupError):
        os.environ.pop('DIGITAL_OCEAN_TOKEN')
        api_token_from_env()
