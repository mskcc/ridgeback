import os
import git
import shutil
import logging
from submitter.app.cache.github_cache import GithubCache


class App(object):
    def factory(app):
        if app.get("github"):
            repo = app["github"]["repository"]
            entrypoint = app["github"]["entrypoint"]
            version = app["github"].get("version", "master")
            return GithubApp(repo, entrypoint, version)
        elif app.get("base64"):
            raise Exception("Base64 app not implemented yet")
        elif app.get("app"):
            raise Exception("Json app not implemented yet")
        else:
            raise Exception("Invalid app reference type")

    factory = staticmethod(factory)

    def resolve(self, location):
        pass

    def _cleanup(self, location):
        shutil.rmtree(location)


class GithubApp(App):
    type = "github"
    logger = logging.getLogger(__name__)

    def __init__(self, github, entrypoint, version="master"):
        super().__init__()
        self.github = github
        self.entrypoint = entrypoint
        self.version = version

    def resolve(self, location):
        dirname = os.path.join(location, self._extract_dirname_from_github_link())
        cached = GithubCache.get(self.github, self.version)
        if cached:
            self.logger.info("App found in cache %s" % cached)
            os.symlink(cached, dirname)
        elif not os.path.exists(dirname):
            git.Git(location).clone(self.github, "--branch", self.version, "--recurse-submodules")
        return os.path.join(dirname, self.entrypoint)

    def get_app_path(self, location):
        dirname = os.path.join(location, self._extract_dirname_from_github_link())
        return os.path.join(dirname, self.entrypoint)

    def _extract_dirname_from_github_link(self):
        dirname = self.github.rsplit("/", 2)[1] if self.github.endswith("/") else self.github.rsplit("/", 1)[1]
        if dirname.endswith(".git"):
            dirname = dirname[:-4]
        return dirname
