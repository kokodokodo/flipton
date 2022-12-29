# flipton
An automatic instance switcher wrapping Mastodon queries with [Mastodon.py](https://github.com/halcy/Mastodon.py). 

As mastodon works as a federated network of instances, information on a specific user (e.g. on their followers) 
may be incomplete at a specific instance, which isn't their home instance. In order to obtain the most complete
information (and perhaps reduce your quota usage on individual instances), flipton automatically automatically 
sends requests to the respective home instances of the specified user.

# Setup
`git clone https://github.com/kokodokodo/flipton <FLIPTON_DIR>`

Add `<FLIPTON_DIR>` to your PYTHONPATH. 

# Usage
In your project, do something like this:

```
from flipton import MastodonInstanceSwitcher
mst = MastodonInstanceSwitcher()

# Your Mastodon.py code

```

For requests, which do not require a logged-in user, you can use the `MastodonInstanceSwitcher` object just like you 
would use a `Mastodon` object from Mastodon.py. However, instead of using user-ids, as you would for Mastodon.py,
in flipton you should specifiy either the instance's hostname (e.g. `mastodon.social`) or the user's account 
name (`username@hostname`). This information allows flipton to address the request to the respective instance.

That means, instead of calling `mst.instance_activity()` (as you would for the instance-specific Mastodon-object) 
you'd call `mst.instance_activity("mastodon.social")` and instead of `mst.account_followers(user_id)` 
you'd call `mst.account_followers("username@hostname")`.





