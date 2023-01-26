import os
import pickle
from pathlib import Path

from urllib3.util.url import parse_url
from mastodon import Mastodon
from mastodon.utility import AttribAccessList
from mastodon.errors import MastodonError

DEBUG = False

# Methods not associated to a logged in user.
# From API version 3.5.5
MASTODON_PUBLIC_API = \
['account', 
 'account_featured_tags',
 'account_followers', 
 'account_following', 
 'account_lookup', 
 'account_statuses',  
 'announcements', 
 'app_verify_credentials',
 'create_app', 
 'custom_emojis',
 'directory', 
 'fetch_next',
 'fetch_previous', 
 'fetch_remaining',
 'instance',
 'instance_activity',
 'instance_health',
 'instance_nodeinfo',
 'instance_peers',
 'instance_rules',
 'poll', 
 'retrieve_mastodon_version', 
 'revoke_access_token',
 'search',
 'set_language',
 'status', 
 'status_card', 
 'status_context', 
 'status_favourited_by', 
 'status_history', 
 'status_reblogged_by', 
 'timeline_hashtag',
 'timeline_home',
 'timeline_local',
 'timeline_public',
 'trending_links',
 'trending_statuses',
 'trending_tags',
 'trends',
 'verify_minimum_version']

APP_NAME = "flipton"


class FliptonError(Exception):
    """ Flipton error class """


class MastodonInstanceSwitcher(object):
    def __init__(self, home_dir=None, use_app_tokens=False):
        '''
        home_dir - base directory to work in, atm only relevant to create an app_token cache if use_app_tokens==True
        '''
        self.use_app_tokens = use_app_tokens
        if self.use_app_tokens:
            self._init_home_dir(home_dir)
            self._init_app_tokens()
        elif home_dir is not None:
            print("MastodonInstanceSwitcher: Ignoring parameter 'home_dir' (not needed if not using app tokens).")
        # Previously instantiated clients
        self.clients = {}
        # Currently active client
        self.active_host = None
        # Previously used host (used to ensure host persistence for 'fetch_'-convinience methods)
        self.previous_host = None
        # Cache for user ids
        self.acct_ids = {}
        
    
    @staticmethod
    def _create_app(host):
        mst = Mastodon(api_base_url=host)
        app_id, app_secret = mst.create_app(api_base_url=host, client_name=APP_NAME, scopes=['read'])
        token = {"id": app_id, "secret": app_secret}
        print("MastodonInstanceSwitcher: Created app token for '%s'"%host)
        return token
    
    
    def _init_home_dir(self, home_dir):
        if home_dir is None:
            home_dir = os.getcwd()
            print("MastodonInstanceSwitcher: Using current working directory '%s' as home dir."%home_dir)
        self.home = Path(home_dir)
        if not self.home.exists():
            print("MastodonInstanceSwitcher: Creating home directory '%s'."%self.home)
            os.makedirs(self.home)
        else:
            print("MastodonInstanceSwitcher: Using home directory '%s'."%self.home)
    
        
    def _init_app_tokens(self):
        # Use app token to retrieve info from different hosts
        self.cache_dir = self.home / "cache/"
        os.makedirs(self.cache_dir, exist_ok=True)
        # App tokens for different hosts
        self.app_token_file = self.cache_dir / "app_tokens.pickle"
        # App tokens for different hosts
        if self.app_token_file.exists():
            # Retrieve stored tokens
            with open(self.app_token_file, "rb") as f:
                self.app_tokens = pickle.load(f)
        else:
            self.app_tokens = {}
        
        
    def set_host(self, hostname):
        if hostname is None:
            self.active_host = None
            return
        # Activate client given host
        host = parse_url(hostname).hostname
        self.previous_host = host
        if self.active_host == host:
            return
        # Check if it has been instantiated already (or failed to instantiate before)
        if host in self.clients:
            if self.clients[host] is None:
                # Indicates failed previous client creation
                print(f"MastodonInstanceSwitcher: Couldn't instantiate client for host '{host}'")
                self.active_host = None
            else:
                self.active_host = host
            return
        # Get app token for instantiation
        if self.use_app_tokens:
            token = self._get_app_token(host)
            if token is None:
                # Only try creating a token once per session
                self.clients[host] = None
                self.active_host = None
                return
            masto_args = dict(client_id=token["id"], client_secret=token["secret"], api_base_url=host)
        else:
            masto_args = dict(api_base_url=host)
        # Successfully retrieved token
        try:
            self.clients[host] = Mastodon(**masto_args)
        except MastodonError as e:
            print(f"MastodonInstanceSwitcher: Failed to instantiate client for host '{host}'")
            print("   Error: %s"%str(e))
            self.clients[host] = None
            self.active_host = None
        
        if DEBUG:
            print(f"MastodonInstanceSwitcher: Instantiated client for host '{host}'")
        self.active_host = host
    
    
    def _get_app_token(self, host):
        token = self.app_tokens.get(host, None)
        if token is None:
            try:
                token = self._create_app(host)
            except MastodonError as e:
                print("MastodonInstanceSwitcher: Error when creating app token at '%s': %s"%(host,str(e)))
                return None
            print(f"MastodonInstanceSwitcher: Created new app token for '{host}': {token}")
            self.app_tokens[host] = token
            # Update token storage
            with open(self.app_token_file, "wb") as file:
                pickle.dump(self.app_tokens, file)
            print(f"   Saved to '{self.app_token_file}'")
        return token
    
    
    def get_acct_id(self, user, host):
        acct = "@".join((user,host))
        # Lookup account in cache
        if acct in self.acct_ids:
            acct_id = self.acct_ids[acct]
            if acct_id is None:
                print(f"MastodonInstanceSwitcher: No id for account '{acct} on {host}'")
            return acct_id
        # Request id for account
        orig_host = self.active_host
        self.set_host(host)
        if self.active_host is None:
            print(f"MastodonInstanceSwitcher: Error looking up account '{acct}': Couldn't connect to host {host}.") 
            self.set_host(orig_host)
            return None
        try:
            acct_dict = self.clients[self.active_host].account_lookup(acct)
            acct_id = acct_dict["id"]
        except Exception as e:
            print(f"MastodonInstanceSwitcher: Error looking up account '{acct}': %s"%str(e))   
            acct_id = None 
        finally:
            self.set_host(orig_host)
        self.acct_ids[acct] = acct_id
        return acct_id
    
    
    def _call_client(self, method_name, **kwargs):
        # Call client method
        client = self.clients[self.active_host]
        client_method = getattr(client, method_name)
        try:
            response = client_method(**kwargs)
        except MastodonError as e:
            raise FliptonError(f"Error when calling '{method_name}()' at '{self.active_host}': %s"%str(e))
        return response
            
    
    
def generate_account_method(method_name):
    def method(self, acct=None, **kwargs):
        # Account specific function
        orig_host = self.active_host
        if isinstance(acct, int):
            # acct already passed as id
            print(f"MastodonInstanceSwitcher.{method_name}(): Interpreting numerical value of 'acct' as user id.")
            acct_id = acct
        else:
            if acct is None:
                if "id" in kwargs:
                    print(f"MastodonInstanceSwitcher.{method_name}() Found 'id' in method arguments, but not 'acct'.\n" 
                          "All 'account_'-methods of MastodonInstanceSwitcher require a parameter 'acct'.\n"
                          "You may pass a numerical user-id via 'acct' on the home instance.")
                raise FliptonError(f"MastodonInstanceSwitcher.'{method_name}()' requires parameter 'acct'.")
            if acct[0]=="@":
                # Remove @-prefix
                acct = acct[1:]
            asplit = acct.split("@")
            if len(asplit) == 1:
                user, host = asplit[0], None
            elif len(asplit) == 2:
                user, host = asplit
            else:
                raise FliptonError(f"Error: MastodonInstanceSwitcher.{method_name}(), parameter 'acct' must have the format 'user@host' (or 'user' for active instance)")
            if host is None:
                if self.active_host is None:
                    raise FliptonError(f"Error: MastodonInstanceSwitcher.{method_name}(), parameter 'acct' must have the format 'user@host' if no active client is present")
                else:
                    host = self.active_host
            else:
                self.set_host(host)
                
            if self.active_host is None:
                self.active_host = orig_host
                raise Exception(f"MastodonInstanceSwitcher.{method_name}(): Failed to connect to host for account '{acct}'")
    
            acct_id = self.get_acct_id(user, host)
            if acct_id is None:
                self.active_host = orig_host
                raise FliptonError(f"MastodonInstanceSwitcher.{method_name}(): Failed to retrieve id for account '{acct}'")
        
        try:
            if method_name == "account_lookup":
                response = self._call_client("account", **{**{"id": acct_id}, **kwargs})
            else:
                response = self._call_client(method_name, **{**{"id": acct_id}, **kwargs})
        except MastodonError as e:
            raise FliptonError(f"MastodonInstanceSwitcher.{method_name}(): Request for '{acct}' failed with error: %s"%str(e))
        finally:
            self.active_host = orig_host
        return response
    
    return method
    
    
def generate_instance_method(method_name):
    def method(self, host=None, **kwargs):
        orig_host = self.active_host
        if isinstance(host, AttribAccessList):
            # Tweak to handle 'fetch_xyz()' utility methods
            assert(method_name[:6] == "fetch_")
            kwargs["first_page"] = host
            host = self.previous_host
        elif host is None:
            if self.active_host is None:
                raise FliptonError(f"MastodonInstanceSwitcher.{method_name}() requires parameter 'host' if no active host is designated.")
            else:
                host = self.active_host
        self.set_host(host)
        
        if self.active_host is None:
            self.active_host = orig_host
            raise FliptonError(f"MastodonInstanceSwitcher.{method_name}(): Failed to connect to host '{host}'")
        
        # Call client method
        try:
            response = self._call_client(method_name, **kwargs)
        except MastodonError as e:
            raise FliptonError(f"MastodonInstanceSwitcher.{method_name}(): Request on '{host}' failed with error: %s"%str(e))
        finally:
            self.active_host = orig_host
        return response
    
    return method
    
        
for method_name in MASTODON_PUBLIC_API:
    if method_name[:8] == "account_":
        method = generate_account_method(method_name)
    else:
        method = generate_instance_method(method_name)
    setattr(MastodonInstanceSwitcher, method_name, method)
    
    

