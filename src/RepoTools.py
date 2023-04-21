import requests
from bs4 import BeautifulSoup
import base64
import pandas as pd
from github import Github
from tqdm import tqdm
import pickle
import pandas as pd
from github.GithubException import UnknownObjectException
from config import * 
import os, sys 

class RepoTools:
    github = Github(TOKEN)

    @staticmethod
    def getPAT():
        return TOKEN
    
    @staticmethod
    def savePaperNameFromGithubUser(username):
        """
        Saves the paper names from the github user's repos with repo name as the key in csv file
        args: username
        returns: None
        """
        
        # Get the user
        user = RepoTools.github.get_user(username)

        # Get their repos
        repos = RepoTools.getReposFromUser(user)
        
        # Get the readme from each repo
        repoWithReadmes = RepoTools.getRepoWithReadmes(repos)

        # Get the paper name for each repo name and save it in df
        paperWithRepoDf = RepoTools.getPaperNameFromRepoURLWithReadmes(repoWithReadmes)
    
    @staticmethod
    def getPaperWithRepoDfFromREADME(repoWithReadmes):
        """
        Gets the paper name from readme and saves it in a dataframe with repo name as the key
        args:
            repoWithReadmes: list of dict with repo object and readme object
        returns:
            paperWithRepoDf: dataframe with repo name as the key and paper name as the value
        """
        pass
    
    @staticmethod
    def getReposFromUser(user):
        """
        Gets the repos from the github user
        args: 
            user : github user object
        returns:
            repos: list of repo objects
        """
        # Get the repos with the user (consider pages as well)
        repos = []
        # one page has 30 repos
        totalPage = user.get_repos().totalCount // 30 + 1

        for page in tqdm(range(totalPage)):
            print(f"Page: {page}/{totalPage}")
            for repo in user.get_repos().get_page(page):
                repos.append(repo)

        return repos

    @staticmethod
    def getRepoWithReadmes(repos):
        """
        Gets the repo and readme from the repos
        args: 
            repos: list of repos
        returns: 
            repoWithReadmes: list of dict with repo object and readme object
        """
        repoWithReadmes = []
        for repo in tqdm(repos):
            readme = RepoTools.getReadmeFromRepo(repo)
            if readme:
                repoWithReadmes.append({"repoURL": repo, "readme": readme})
        
        return repoWithReadmes

    @staticmethod
    def getReadmeFromRepo(repo):
        """
        Gets the readme from the repo
        args: repo
        returns: readme
        """
        try:
            readme = repo.get_readme()
        except UnknownObjectException:
            return None
        return readme
    


