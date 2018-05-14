from . import server
from . import users

from invoke import Collection

ns = Collection()
ns.add_collection(users)
ns.add_collection(server)
