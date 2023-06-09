import requests
from bs4 import BeautifulSoup
import base64
import pandas as pd
import numpy as np
from github import Github
from tqdm import tqdm
import pickle
import pandas as pd
from github.GithubException import UnknownObjectException, GithubException
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
    arxivDataset = pd.read_csv(os.path.join(os.curdir, "../data/arxiv.csv"))
    

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
            try:
                readme = str(repoWithReadme["readme"].decoded_content.decode("utf-8"))
            except AssertionError:
                readme = ""

            repoName = repoWithReadme["repo"].full_name
            # try to find the title using the patterns
            paperTitles = RepoTools.getPaperTitlesFromReadme(readme)
            arxivLinks = RepoTools.getArxivLinksFromReadme(readme)
            arxivPaperTitles = RepoTools.getPaperTitlesFromArxivLinks(repoName, arxivLinks)

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
            except GithubException:
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
            try:
                readme = str(repoWithReadme["readme"].decoded_content.decode("utf-8"))
            except AssertionError:
                readme = ""
            repoName = repoWithReadme["repo"].full_name
            githubLinks.extend(RepoTools.getGithubLinksFromReadme(repoName, readme))

        return np.unique(githubLinks)


    @staticmethod
    def getGithubLinksFromReadme(repoName, readme):
        """
        Gets the github links from the readme
        args:
            repoName: name of the repo
            readme: readme of the repo
        """
        link_patterns = [r'https://github.com/([\w\-]*/[\w\-]*)']
        githubLinks = []
        for link_pattern in link_patterns:
            links = re.findall(link_pattern, readme)
            if len(links) > 0:
                githubLinks.extend(links)

        if len(githubLinks) > 5:
            print(f"Found more than 5 github links in https://github.com/{repoName}. Ignoring all of them. Please check the readme")
            return []
        return githubLinks
    
    @staticmethod
    def getPaperTitlesFromReadme(readme):
        title_patterns = [r'[^k][tT]itle\s*=\s*{\s*(.*)\s*}', r'[^k][tT]itle\s*=\s*"\s*(.*)\s*"']
        paperTitles = []
        for title_pattern in title_patterns:
                titles = re.findall(title_pattern, readme)
                if len(titles) > 0:
                    # if found the title and title has at least 3 words
                    titles = [title for title in titles if len(title.split()) > 2]
                    # remove all instances of '{' and '}' from titles
                    titles = [str(title).replace('{', '').replace('}', '') for title in titles]
                    paperTitles.extend(titles)

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
            try:
                readme = RepoTools.getReadmeFromRepo(repo)
            except GithubException:
                print(f"Could not find readme for {repo.full_name}")
                readme = None
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
            print('Could not find readme for this link : ' + repo.html_url)
            return None
        except GithubException:
            print('Could not find readme for this link : ' + repo.html_url)
            return None
        return readme
    
    
    @staticmethod
    def getArxivLinksFromReadme(readme):
        """
        Gets the arxiv link from the readme
        args: readme
        returns: arxivLink
        """
        linkPatterns = [r'arxiv\.org/abs/(\d{4}\.\d{4,5})', r'arxiv\.org/pdf/(\d{4}\.\d{4,5})']
        arxivLinks = []
        for linkPattern in linkPatterns:
            links = re.findall(linkPattern, readme)
            links = ["https://arxiv.org/abs/" + link for link in links]
            if len(links) > 0:
                # paperTitles.extend(titles)
                arxivLinks.extend(links)

        return np.unique(arxivLinks)
    
    @staticmethod
    def getPaperTitlesFromArxivLinks(repoName, arxivLinks):
        """
        Gets the paper title from the arxiv link
        args: 
            repoName : name of the repo
            arxivLinks : list of arxiv links
        returns: paperTitles
        """
        paperTitles = []
        # get only unique ones
        arxivLinks = np.unique(arxivLinks)
        if len(arxivLinks) > 10:
            print(f'Found more than 10 arxiv links in the readme of https://github.com/{repoName}. Ignoring the links')
            return paperTitles
        for arxivLink in arxivLinks:
            if arxivLink:
                paperTitle = RepoTools.getPaperTitleFromArxivLink(arxivLink)
                if paperTitle: 
                    paperTitles.append(paperTitle)
        
        return paperTitles
    
    @staticmethod
    def getPaperTitleFromArxivLink(arxivLink):
        """
        Gets the paper title from the arxiv link
        args: arxivLink
        returns: paperTitle
        """

        id = float(arxivLink[22:])
        # return the title (only 1 ) from the arxiv dataset using id (if the id exists)
        if id in RepoTools.arxivDataset['id'].values:
            return RepoTools.arxivDataset[RepoTools.arxivDataset['id'] == id]['title'].values[0].replace("\n ", "")

        # otherwise just get it from the internet
        arxivLink = "https://export." + arxivLink[8:]
        response = requests.get(arxivLink)
        
        # extract paper title using regular expressions
        title_regex = re.compile('<title>\[\d{4}.\d{4,5}]\s*(.*)</title>')
        title_match = title_regex.search(response.text)
        # try to get the title from the response without exception
        try:
            paper_title = title_match.group(1)
        except AttributeError:
            print(f"Could not find the paper title in {arxivLink}")
            paper_title = None
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
    def loadReposWithReadmeAndGetExtendedData(username, saveExtendedRepoWithReadme):
        repoWithReadmes = RepoTools.loadPickle(f'{username}RepoWithReadmes')
        extendedRepoWithReadmesAndData = RepoTools.getDataFromReadmes(repoWithReadmes)
        if saveExtendedRepoWithReadme:
            RepoTools.saveAsPickle(extendedRepoWithReadmesAndData, "extended_" + f'{username}RepoWithReadmes')
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
        forks = []
        stargazers_counts = []
        created_ats = []
        open_issues_counts = []
        names = []

        # sort the data based on the number of arxiv papers
        sortedData = sorted(extendedRepoWithReadmesAndData, key = lambda x : len(x['arxivPaperTitles']))

        for repoData in sortedData:
            repoLink = 'https://github.com/' + repoData['repo'].full_name
            forks_count = repoData['repo'].forks_count
            stargazers_count = repoData['repo'].stargazers_count
            created_at = repoData['repo'].created_at
            open_issues_count = repoData['repo'].open_issues_count
            name = repoData['repo'].name
            
            for title in repoData['papers']:
                if not title in paperTitles:
                    paperTitles.append(title)
                    repoLinks.append(repoLink)
                    forks.append(forks_count)
                    stargazers_counts.append(stargazers_count)
                    created_ats.append(created_at)
                    open_issues_counts.append(open_issues_count)
                    names.append(name)
            

            # don't add the arxiv links if the paper title exists and ignoreArxivIfPaperTitleExists is True
            if ignoreArxivIfPaperTitleExists and len(repoData['papers']) > 0:
                continue

            for title in repoData['arxivPaperTitles']:
                if not title in paperTitles:
                    paperTitles.append(title)
                    repoLinks.append(repoLink)
                    forks.append(forks_count)
                    stargazers_counts.append(stargazers_count)
                    created_ats.append(created_at)
                    open_issues_counts.append(open_issues_count)
                    names.append(name)
                    
        df = pd.DataFrame()
        df['title'] = paperTitles
        df['repo_link'] = repoLinks
        df['forks'] = forks
        df['stargazers_count'] = stargazers_counts
        df['created_at'] = created_ats
        df['open_issues_count'] = open_issues_counts
        df['name'] = names

        # we need to drop the rows with href in the title (these are not papers)
        # need to fix this
        try:
            df = df.drop(df[df['title'].str.contains('href')].index)
        except AttributeError:
            print("DF is empty!")
        return df
    
    @staticmethod
    def loadExtendedRepoWithReadmeAndGetPaperDf(username, ignoreArxivIfPaperTitleExists):
        """
        Loads the extended repo with readme and gets the paper dataframe
        args: 
            filename: filename to load the extended repo with readme
            ignoreArxivIfPaperTitleExists: if True, ignores the arxiv link if paper title exists
        """
        extendedRepoWithReadmesAndData = RepoTools.loadPickle(f'extended_{username}RepoWithReadmes')
        return RepoTools.getPaperDfFromExtendedRepoWithReadmesAndData(extendedRepoWithReadmesAndData, ignoreArxivIfPaperTitleExists)