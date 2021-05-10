import os
import git
import logging
from django.conf import settings


class GithubCache(object):
    logger = logging.getLogger(__name__)

    @staticmethod
    def get(github, version):
        expected_path = GithubCache._generate_directory_name(github, version)
        full_dir = os.path.join(
            expected_path, GithubCache._extract_dirname_from_github_link(github)
        )
        GithubCache.logger.info("Looking for pipeline in cache : %s" % full_dir)
        if os.path.exists(full_dir):
            GithubCache.logger.info("Pipeline found in cache : %s" % full_dir)
            return full_dir
        GithubCache.logger.info("Pipeline not found in cache")
        return None

    @staticmethod
    def add(github, version):
        expected_path = GithubCache._generate_directory_name(github, version)
        if not expected_path:
            git.Git(expected_path).clone(
                github, "--branch", version, "--recurse-submodules"
            )
            return expected_path
        return None

    @staticmethod
    def _generate_directory_name(github, version):
        github_name = github.split(".com/")[-1].replace("/", "_")
        path = os.path.join(settings.APP_CACHE, github_name, version)
        return path

    @staticmethod
    def _extract_dirname_from_github_link(github):
        dirname = (
            github.rsplit("/", 2)[1]
            if github.endswith("/")
            else github.rsplit("/", 1)[1]
        )
        if dirname.endswith(".git"):
            dirname = dirname[:-4]
        return dirname
