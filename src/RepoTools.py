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
import re

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

        # save the repoWithReadmes as pickle (just in case)
        RepoTools.saveAsPickle(repoWithReadmes, f"{username}RepoWithReadme")

        # Get the paper name for each repo name and save it in df
        paperWithRepoDf = RepoTools.getPaperWithRepoDfFromREADME(repoWithReadmes)

        return paperWithRepoDf
    
    @staticmethod
    def getPaperWithRepoDfFromREADME(repoWithReadmes):
        """
        Gets the paper name from readme and saves it in a dataframe with repo name as the key
        args:
            repoWithReadmes: list of dict with repo object and readme object
        returns:
            paperWithRepoDf: dataframe with repo name as the key and paper name as the value
        """
        title_patterns = [r'title\s*=\s*{([^}]+\s*)+}', r'title\s*=\s*"([^"]+\s*)+"']
        paperWithRepoURLs = []
        for repoWithReadme in repoWithReadmes:
            
            readme = str(repoWithReadme["readme"].decoded_content.decode("utf-8"))
            repoName = repoWithReadme['repo'].full_name
            # try to find the title using the patterns
            for title_pattern in title_patterns:
                title_matches = re.findall(title_pattern, readme)
                titles = [match.strip() for match in title_matches]
                # if found the title and title has at least 3 words
                if len(titles) > 0 and len(titles[0].split()) > 2:
                    paperWithRepoURL = {"title":titles[0], "url":"https://github.com/"+repoName}
                    paperWithRepoURLs.append(paperWithRepoURL)  

        paperWithRepoDf = pd.DataFrame(paperWithRepoURLs)
        return paperWithRepoDf

    
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
                repoWithReadmes.append({"repo": repo, "readme": readme})
        
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
    
    @staticmethod
    def saveAsPickle(obj, filename):
        """
        Saves the object as pickle
        args: 
            obj: object to be saved
            filename: filename to save the object
        returns: None
        """
        outputPath = os.path.join(os.curdir, "../pickles")  
        if not os.path.exists(outputPath):
            os.mkdir(outputPath)

        with open(os.path.join(outputPath, filename), "wb") as f:
            pickle.dump(obj, f)

    @staticmethod
    def loadPickle(filename):
        """
        Loads the pickle file
        args: filename
        returns: object
        """
        with open(os.path.join(os.curdir, "../pickles", filename), "rb") as f:
            return pickle.load(f)

