import requests
from bs4 import BeautifulSoup
import base64
from github import Github
from tqdm import tqdm
import pickle
import pandas as pd

class DataTools:
    @staticmethod
    def getPAT():
        return "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"
    
    @staticmethod
    def getGithub():
        pat = DataTools.getPAT()
        return Github(pat)
    
    @staticmethod
    def getPaperNameFromLink(link):
        response = requests.get(link, headers = headers)
        readme = response.json()
        # print(readme)
        if readme and "content" in readme:
            decoded_content = base64.b64decode(readme["content"]).decode("utf-8")
            # print(decoded_content)
            while "title" in decoded_content:
                ind = decoded_content.find("title")
                substr = decoded_content[ind : ]
                s = substr.find("{")
                e = substr.find("}")
                decoded_content = substr[e:]              
                print(substr[s + 1:e]) 

    @staticmethod
    def getReadMeFromRepoLink(link):
        '''
            Takes the github repo link and returns the readme in encoded form
        '''
        link = link + "/readme"
        response = requests.get(link, headers = headers)
        readme = response.json()

        if readme and "content" in readme:
            return readme["content"]
        else:
            return ""
        
    @staticmethod
    def getAllReposFromUser(username):
        '''
            Takes the username and returns all repository links
        '''
        g = DataTools.getGithub()
        user = g.get_user(username)
        repoNames = []
        
        totalPage = user.get_repos().totalCount // 30 + 1

        for pageNo in tqdm(range(0, totalPage)):
            print(f"Trying to fetch from page {pageNo + 1}")
            for repo in user.get_repos().get_page(pageNo):
                repoNames.append(repo.full_name)

        return repoNames

    @staticmethod
    def saveAllReposFromUser(username):
        '''
            Takes the username and saves all repo data
        '''
        g = DataTools.getGithub()
        user = g.get_user(username)
        repos = []
        
        totalPage = user.get_repos().totalCount // 30 + 1

        for pageNo in tqdm(range(0, totalPage)):
            print(f"Trying to fetch from page {pageNo + 1}")
            for repo in user.get_repos().get_page(pageNo):
                repos.append(repo)

        # leave the first one 
        repos = repos[1:]
        
        with open(f"{username}Repos", 'wb') as handle:
            pickle.dump(repos, handle, protocol=pickle.HIGHEST_PROTOCOL)


    @staticmethod
    def getDataFrameFromRepoList(repos, getReadMe):
        """
            Arguments:
                repos : list of repository object
                getReadMe : boolean. True if want to fetch readme as well
            Returns:
                dataframe containing useful information
        """
        forks = []
        stargazers_count = []
        created_at = []
        last_modified = []
        networks_count = []
        open_issues_count = []
        subscribers_count = []
        name = []

        for repo in repos:
            forks.append(repo.forks_count)
            stargazers_count.append(repo.stargazers_count)
            created_at.append(repo.created_at)
            # last_modified.append(repo.last_modified)
            # networks_count.append(repo.network_count)
            open_issues_count.append(repo.open_issues_count)
            # subscribers_count.append(repo.subscribers_count)
            name.append(repo.name)
            # to-do readme
        
        df = pd.DataFrame()
        df["name"] = name
        df["forks"] = forks
        df["stars"] = stargazers_count
        df["created_at"] = created_at
        # df["last_modified"] = last_modified
        # df["networks"] = networks_count
        df["open_issues"] = open_issues_count
        # df["subscribers"] = subscribers_count
        
        return df