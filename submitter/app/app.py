import os
import git
import uuid
import shutil
import logging
from django.conf import settings
from django.core.cache import cache
from lib.memcache_lock import memcache_lock


class App(object):

    def factory(app):
        if app.get('github'):
            repo = app['github']['repository']
            entrypoint = app['github']['entrypoint']
            version = app['github'].get('version', 'master')
            return GithubApp(repo, entrypoint, version)
        elif app.get('base64'):
            raise Exception('Base64 app not implemented yet')
        elif app.get('app'):
            raise Exception('Json app not implemented yet')
        else:
            raise Exception('Invalid app reference type')
    factory = staticmethod(factory)

    def resolve(self, location):
        pass

    def _cleanup(self, location):
        shutil.rmtree(location)


class GithubCache(object):
    logger = logging.getLogger(__name__)

    @staticmethod
    def get(github, version):
        GithubCache.logger.info('Looking for App in Cache with %s %s' % (github, version))
        cache_key = GithubCache._cache_key(github, version)
        _app_location = cache.get(cache_key)
        return _app_location if _app_location else None

    @staticmethod
    @memcache_lock('add_app_to_cache')
    def add(github, version):
        GithubCache.logger.info('Add App to Cache with %s %s' % (github, version))
        location = os.path.join(settings.APP_CACHE, str(uuid.uuid4()))
        GithubCache.logger.info("App Cache location %s" % location)
        os.makedirs(location)
        dirname = GithubCache._extract_dirname_from_github_link(github)
        if not os.path.exists(os.path.join(location, dirname)):
            git.Git(location).clone(github, '--branch', version, '--recurse-submodules')
        full_path = os.path.join(location, dirname)
        cache.add(GithubCache._cache_key(github, version), full_path)
        GithubCache.logger.info("App Cache location %s" % full_path)
        return full_path

    @staticmethod
    def _cache_key(github, version):
        return 'github_{link}_{version}'.format(link=github, version=version)

    @staticmethod
    def _extract_dirname_from_github_link(github):
        dirname = github.rsplit('/', 2)[1] if github.endswith('/') else github.rsplit('/', 1)[1]
        if dirname.endswith('.git'):
            dirname = dirname[:-4]
        return dirname


class GithubApp(App):
    type = "github"
    logger = logging.getLogger(__name__)

    def __init__(self, github, entrypoint, version='master'):
        super().__init__()
        self.github = github
        self.entrypoint = entrypoint
        self.version = version

    def resolve(self, location):
        dirname = os.path.join(location, self._extract_dirname_from_github_link())
        cached = GithubCache.get(self.github, self.version)
        if not cached:
            cached = GithubCache.add(self.github, self.version)
            self.logger.info("Adding App to cache %s" % cached)
        os.symlink(cached, dirname)
        return os.path.join(cached, self.entrypoint)

    def _extract_dirname_from_github_link(self):
        dirname = self.github.rsplit('/', 2)[1] if self.github.endswith('/') else self.github.rsplit('/', 1)[1]
        if dirname.endswith('.git'):
            dirname = dirname[:-4]
        return dirname
