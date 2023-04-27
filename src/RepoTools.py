import requests
from bs4 import BeautifulSoup
import base64
import pandas as pd
import numpy as np
from github import Github
from tqdm import tqdm
import pickle
import pandas as pd
from github.GithubException import UnknownObjectException
from config import * 
import os, sys 
import re

class RepoTools:
    """
    Class to get the repo and readme from github user. 
    Use methods to get the repo and readme from github user and save it as pickle, store it in csv or get it as dataframe.
    
    To use it, you must have a github PAT. Get it from https://github.com/settings/tokens -> generate new token
    Copy the token and paste it in config.py file in the TOKEN variable.
    """
    github = Github(TOKEN)

    @staticmethod
    def getPAT():
        return TOKEN
    
    @staticmethod
    def savePaperNameFromGithubUser(username, saveRepoWithReadme, saveExtendedRepoWithReadme):
        """
        Saves the paper names from the github user's repos with repo name as the key in csv file
        args: 
            username: github username
            saveRepoWithReadme: bool to save the repoWithReadme as pickle
            saveExtendedRepoWithReadme: bool to save the extendedRepoWithReadme as pickle
        returns: None
        """
        
        # Get the user
        user = RepoTools.github.get_user(username)

        # Get their repos
        repos = RepoTools.getReposFromUser(user)
        
        
        # Get the readme from each repo
        repoWithReadmes = RepoTools.getRepoWithReadmes(repos)

        # Get the github repos linked in the readme
        extendedRepoWithReadmes = RepoTools.getExtendedReposWithReadmes(repoWithReadmes, repos)

        # save the repoWithReadmes as pickle
        if saveRepoWithReadme:
            RepoTools.saveAsPickle(extendedRepoWithReadmes, f"{username}RepoWithReadmes")


        # Get the paper name for each repo name and save it in df
        extendedRepoWithReadmesAndData = RepoTools.getDataFromReadmes(extendedRepoWithReadmes)

        # save the extendedRepoWithReadmes as pickle
        if saveExtendedRepoWithReadme:
            RepoTools.saveAsPickle(extendedRepoWithReadmesAndData, f"extended_{username}RepoWithReadmes")


        # get papers from extendedRepoWithReadMes and save it in csv where paper name is the key
         
    
        return extendedRepoWithReadmesAndData
    
    @staticmethod
    def getDataFromReadmes(repoWithReadmes):
        """
        Gets the paper name from readme and saves it in a dataframe with repo name as the key
        args:
            repoWithReadmes: list of dict with repo object and readme object
        returns:
            paperWithRepoDf: dataframe with repo name as the key and paper name as the value
        """
        extendedRepoWithReadMes = []
        for repoWithReadme in tqdm(repoWithReadmes): 
            readme = str(repoWithReadme["readme"].decoded_content.decode("utf-8"))
            # try to find the title using the patterns
            paperTitles = RepoTools.getPaperTitlesFromReadme(readme)
            arxivLinks = RepoTools.getArxivLinksFromReadme(readme)
            arxivPaperTitles = RepoTools.getPaperTitlesFromArxivLinks(arxivLinks)

            repoWithReadme.update({"papers": paperTitles, "arxivLinks": arxivLinks, "arxivPaperTitles": arxivPaperTitles})
            extendedRepoWithReadMes.append(repoWithReadme)

        return extendedRepoWithReadMes

    @staticmethod
    def getExtendedReposWithReadmes(repoWithReadmes, repos):
        """
        Gets the extended repos with readmes
        args:
            repoWithReadmes: list of dict with repo object and readme object
            repos: list of repo objects
        returns:
            extraRepos: list of repo objects
        """
        print('Fetching the extra github links and readmes from the repoWithReadme')
        githubLinks = RepoTools.getGithubLinksFromRepoWithReadmes(repoWithReadmes)
        extraRepos = []
        
        for link in tqdm(githubLinks):
            try :
                extraRepos.append(RepoTools.github.get_repo(link))
            except UnknownObjectException:
                print('Could not find repository for this link : ' + link)
        extraRepos = [repo for repo in extraRepos if repo not in repos]
        extraRepoWithReadmes = RepoTools.getRepoWithReadmes(extraRepos)
        repoWithReadmes.extend(extraRepoWithReadmes)
        
        return repoWithReadmes
    
    @staticmethod
    def getGithubLinksFromRepoWithReadmes(repoWithReadmes):
        """
        Gets the github links from the repoWithReadmes
        args: 
            repoWithReadmes: list of dict with repo object and readme object
        returns: 
            githubLinks: list of github links
        """
        githubLinks = []
        for repoWithReadme in repoWithReadmes:
            readme = str(repoWithReadme["readme"].decoded_content.decode("utf-8"))

            githubLinks.extend(RepoTools.getGithubLinksFromReadme(readme))

        return np.unique(githubLinks)


    @staticmethod
    def getGithubLinksFromReadme(readme):
        link_patterns = [r'https://github.com/([\w\-]*/[\w\-]*)']
        githubLinks = []
        for link_pattern in link_patterns:
            links = re.findall(link_pattern, readme)
            if len(links) > 0:
                githubLinks.extend(links)

        if len(githubLinks) > 5:
            print('Found more than 5 github links in the readme. Ignoring the links')
            return []
        return githubLinks
    
    @staticmethod
    def getPaperTitlesFromReadme(readme):
        title_patterns = [r'[^k]title\s*=\s*{\s*(.*)\s*}', r'[^k]title\s*=\s*"\s*(.*)\s*"']
        paperTitles = []
        for title_pattern in title_patterns:
                titles = re.findall(title_pattern, readme)
                # if found the title and title has at least 3 words
                if len(titles) > 0:
                    # paperTitles.extend(titles)
                    paperTitles.extend([title for title in titles if len(title.split()) > 2])

        return paperTitles
    

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
        print('Fetching the readmes from the repos')
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
    def getArxivLinksFromReadme(readme):
        """
        Gets the arxiv link from the readme
        args: readme
        returns: arxivLink
        """
        linkPatterns = [r'(arxiv\.org/abs/\d{4}\.\d{4,5})']
        arxivLinks = []
        for linkPattern in linkPatterns:
            links = re.findall(linkPattern, readme)
            links = ["https://" + link for link in links]
            if len(links) > 0:
                # paperTitles.extend(titles)
                arxivLinks.extend(links)

        return arxivLinks
    
    @staticmethod
    def getPaperTitlesFromArxivLinks(arxivLinks):
        """
        Gets the paper title from the arxiv link
        args: arxivLinks
        returns: paperTitles
        """
        paperTitles = []
        if len(arxivLinks) > 10:
            print("Too many arxiv links (10), skipping")
            return paperTitles
        for arxivLink in arxivLinks:
            paperTitles.append(RepoTools.getPaperTitleFromArxivLink(arxivLink))
        
        return paperTitles
    
    @staticmethod
    def getPaperTitleFromArxivLink(arxivLink):
        """
        Gets the paper title from the arxiv link
        args: arxivLink
        returns: paperTitle
        """
        response = requests.get(arxivLink)

        # extract paper title using regular expressions
        title_regex = re.compile('<title>\[\d{4}.\d{4,5}]\s*(.*)</title>')
        title_match = title_regex.search(response.text)
        paper_title = title_match.group(1)
        return paper_title

    
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


    @staticmethod
    def loadReposWithReadmeAndGetExtendedData(filename, saveExtendedRepoWithReadme):
        repoWithReadmes = RepoTools.loadPickle(filename)
        extendedRepoWithReadmesAndData = RepoTools.getDataFromReadmes(repoWithReadmes)
        if saveExtendedRepoWithReadme:
            RepoTools.saveAsPickle(extendedRepoWithReadmesAndData, "extended_" + filename)
        return extendedRepoWithReadmesAndData
    
    @staticmethod
    def getPaperDfFromExtendedRepoWithReadmesAndData(extendedRepoWithReadmesAndData, ignoreArxivIfPaperTitleExists):
        """
        Gets the paper dataframe from the extendedRepoWithReadmesAndData
        args: 
            extendedRepoWithReadmesAndData: list of dict with repo object and readme object
            ignoreArxivIfPaperTitleExists: if True, ignores the arxiv link if paper title exists
        """
        paperTitles = []
        repoLinks = []
        
        # sort the data based on the number of arxiv papers
        sortedData = sorted(extendedRepoWithReadmesAndData, key = lambda x : len(x['arxivPaperTitles']))

        for repoData in sortedData:
            repoLink = 'https://github.com/' + repoData['repo'].full_name
            for title in repoData['papers']:
                if not title in paperTitles:
                    paperTitles.append(title)
                    repoLinks.append(repoLink)

            # don't add the arxiv links if the paper title exists and ignoreArxivIfPaperTitleExists is True
            if ignoreArxivIfPaperTitleExists and len(repoData['papers']) > 0:
                continue

            for title in repoData['arxivPaperTitles']:
                if not title in paperTitles:
                    paperTitles.append(title)
                    repoLinks.append(repoLink)
                    
        df = pd.DataFrame()
        df['title'] = paperTitles
        df['repo_link'] = repoLinks

        # we need to drop the rows with href in the title (these are not papers)
        # need to fix this
        df = df.drop(df[df['title'].str.contains('href')].index)
        return df
    
    @staticmethod
    def loadExtendedRepoWithReadmeAndGetPaperDf(filename, ignoreArxivIfPaperTitleExists):
        """
        Loads the extended repo with readme and gets the paper dataframe
        args: 
            filename: filename to load the extended repo with readme
            ignoreArxivIfPaperTitleExists: if True, ignores the arxiv link if paper title exists
        """
        extendedRepoWithReadmesAndData = RepoTools.loadPickle(filename)
        return RepoTools.getPaperDfFromExtendedRepoWithReadmesAndData(extendedRepoWithReadmesAndData, ignoreArxivIfPaperTitleExists)