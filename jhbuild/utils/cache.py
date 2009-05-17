import os

BASE_DIR = os.path.expanduser('~/.jhdebuild/cache/')
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

def get_cached_value(key):
    fn = os.path.join(BASE_DIR, key)
    if os.path.exists(fn):
        return file(fn).read()
    return None


def write_cached_value(key, value):
    fn = os.path.join(BASE_DIR, key)
    file(fn, 'w').write(value)

