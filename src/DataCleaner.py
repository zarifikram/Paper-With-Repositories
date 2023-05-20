import math
import os
import time
import pickle
from typing import List
import pandas as pd
from requests import ConnectTimeout, ReadTimeout
from urllib3 import HTTPSConnectionPool
from Extractor import Extractor
from tqdm import tqdm 
from github import Repository
from DataTools import DataTools
from github.GithubException import GithubException, RateLimitExceededException

class DataCleaner:
    """
        Responsible for making a CSV file for each cid with year with the number of matched repos
        Also makes a CSV file for each cid with matched papers along with all the info
    """

    
    companyToRepos = Extractor.getConfig()
    
    @staticmethod
    def getAllMatchingPapersInfo(companyDf):
        """
            Returns a df with all the matched papers info
        """
        cids = DataCleaner.getUniqueCids(companyDf)
        dfs = []
        for cid in tqdm(cids):
            df = DataCleaner.getMatchingPaperInfoByCid(companyDf, cid)
            dfs.append(df)
        
        finalDf = pd.concat(dfs, ignore_index=True)

        finalDf.drop(columns=['key_0', 'title', 'lowerTitle', 'stargazers_count', 'forks', 'open_issues_count'], inplace=True)
        return finalDf
    
    @staticmethod
    def getMatchingPaperInfoByCid(companyDf, cid):
        """
            Returns a df with all the matched papers info for the given cid
        """
        companies = DataCleaner.getCompaniesFromCid(companyDf, cid)
        paperFromCompanyRepos = Extractor.loadCSVFromOutput(companies)
        dfByCid = DataCleaner.getDfByCidAndYear(companyDf, cid)
        matchedPapersDf = DataCleaner.getMatchedPapers(dfByCid, paperFromCompanyRepos)

        # need to join matchedPaperDf with cid repos
        repoInfoByCid = DataCleaner.getRepoInfoDfByCid(companyDf, cid, ignoreNonUser = False)
        repoInfoByCid['repo_link'] = 'https://github.com/' + repoInfoByCid['Full Name']
        # print(matchedPapersDf)
        merged_data = matchedPapersDf.merge(repoInfoByCid, how='left', on = 'repo_link')
 
        return merged_data
    @staticmethod
    def getInfoDfFromCidAndYear(companyDf):
        cids = DataCleaner.getUniqueCids(companyDf)
        years = DataCleaner.getUniqueYears(companyDf)
        dfs = []
        for cid in tqdm(cids):
            df = DataCleaner.analyzeByCid(companyDf, cid, years)
            dfs.append(df)
        
        finalDf = pd.concat(dfs)
        return finalDf

    @staticmethod
    def analyzeByCid(companyDf, cid, years):
        """
            Analyzes the given cid for the given years
        """
        cidYearDicts = []
        companies = DataCleaner.getCompaniesFromCid(companyDf, cid)
        paperFromCompanyRepos = Extractor.loadCSVFromOutput(companies)
        dfByCid = DataCleaner.getDfByCidAndYear(companyDf, cid)
        repoInfoByCid = DataCleaner.getRepoInfoDfByCid(companyDf, cid, ignoreNonUser = True)
        matchedPapersDf = DataCleaner.getMatchedPapers(dfByCid, paperFromCompanyRepos)
        matchedRepoInfoByCid = DataCleaner.getMatchedRepoInfo(repoInfoByCid, matchedPapersDf)
        for year in years:
            nMatchPapersByCidInYear = DataCleaner.getNumberOfRowsByYear(matchedPapersDf, year)
            repoTotalInfoinYear = DataCleaner.getRepoInfoInYear(repoInfoByCid, year)
            matchedRepoTotalInfoinYear = DataCleaner.getRepoInfoInYear(matchedRepoInfoByCid, year, matched = True)
            nPapersInTheYear = DataCleaner.getNumberOfRowsByYear(dfByCid, year)
            cidYearDict = {"CID": cid, "Year": year, "MatchedPapers": nMatchPapersByCidInYear, "TotalPapers": nPapersInTheYear}
            cidYearDict.update(repoTotalInfoinYear)
            cidYearDict.update(matchedRepoTotalInfoinYear)
            cidYearDicts.append(cidYearDict)
        return pd.DataFrame(cidYearDicts)

    @staticmethod
    def getMatchedRepoInfo(repoInfoByCid, matchedPaperDf):
        repoNames = list(matchedPaperDf.name.unique())
        return repoInfoByCid[repoInfoByCid['Full Name'].str.contains('|'.join(repoNames))]
    
    @staticmethod
    def getRepoInfoInYear(df, year, matched = False):
        df = df[df.YearCreated == year]
        df = df.drop(['Full Name', 'YearCreated'], axis = 1)
        totalRepoInfo = dict(df.sum())
        totalRepoInfo.update({'Repos Created' : len(df)})
        if matched:
            matchedRepoInfo = {}
            for _ in totalRepoInfo.items():
                key, value = _
                matchedRepoInfo['Matched ' + key] = value
            return matchedRepoInfo
        return totalRepoInfo
    
    @staticmethod
    def repoInfoCreatedInTheYear(repos, year):
        """
            Returns the number of repos created in the given year and total number of 
            forks, stars, watchers, commits, branches, contributors, open issues, pull requests, and projects of repos created in the given year
        """
        reposInTheYear = [repo for repo in repos if repo.created_at.year == year]
        nReposInTheYear = len(reposInTheYear)
        nForks = 0
        nStars = 0
        nWatchers = 0
        nCommits = 0
        nBranches = 0
        nReleases = 0
        nContributors = 0
        nIssues = 0
        nPullRequests = 0
        nProjects = 0

        for repo in tqdm(reposInTheYear):
            nForks += repo.forks_count
            nStars += repo.stargazers_count
            nWatchers += repo.watchers_count
            nCommits += repo.get_commits().totalCount
            nBranches += repo.get_branches().totalCount
            # nContributors += repo.get_contributors().totalCount
            nIssues += repo._open_issues_count
            # nPullRequests += repo.get_pulls().totalCount


        return {"ReposCreated": nReposInTheYear, "Forks": nForks, "Stars": nStars, "Watchers": nWatchers, "Commits": nCommits, "Branches": nBranches, "Releases": nReleases, "Contributors": nContributors, "Open Issues": nIssues, "PullRequests": nPullRequests, "Projects": nProjects}
    
    @staticmethod
    def getUniqueCids(companyDf):
        """
            Returns the unique cids in the main dataset
        """
        return list(companyDf["CID"].unique())
    
    @staticmethod
    def getUniqueYears(companyDf):
        """
            Returns the unique years in the main dataset
        """
        uniqueYears = list(companyDf["Year"].unique())
        uniqueYears.sort()
        return uniqueYears
    
    @staticmethod
    def getDfByCidAndYear(companyDf, cid, year = None):
        """
            Returns the df for the given cid and year
        """
        df = companyDf
        if year:
            df = df[(df["CID"] == cid) & (df["Year"] == year)]
        else:
            df = df[df["CID"] == cid]
        
        return df
    
    @staticmethod
    def getCompaniesFromCid(companyDf, cid):
        """
            Returns the company name from cid
        """
        df = companyDf
        df = df[df["CID"] == cid]
        return list(df["Company"].unique())
    
    @staticmethod
    def getMatchedPapers(df, paperFromCompanyRepos):
        """
            Returns the matched papers df for the given df
        """
        # paperTitles = [title.lower() for title in paperFromCompanyRepos['Title']]
        merged_data = df.merge(paperFromCompanyRepos, how='inner', left_on=df['Title'].str.lower(), right_on=paperFromCompanyRepos['title'].str.lower())
        # drop duplicate titles
        merged_data.drop_duplicates(subset=['key_0'], inplace=True)
        return merged_data

    @staticmethod
    def getCidFromCompany(companyDf, company):
        """
            Returns the cid from company name
        """
        df = companyDf
        df = df[df["Company"] == company]
        return df["CID"].iloc[0]
    
    @staticmethod
    def getNumberOfRowsByYear(df, year):
        """
            Returns the number of rows in the given df for the given year
            *** assumes the df contains the year column ***
        """
        return df[df["Year"] == year].Year.count()
    
    @staticmethod
    def getUsernamesByCid(companyDf, cid):
        """
            Returns the usernames for the given cid from CompanyTORepos.json
        """
        companies = DataCleaner.getCompaniesFromCid(companyDf, cid)
        users = []
        for companyToRepo in DataCleaner.companyToRepos:
            if companyToRepo["company"] in companies:
                users.extend(companyToRepo["repos"])
            
        return users
            
    @staticmethod
    def getRepoInfos(companyDf):
        """
            Returns the repo info for all the companies in the given df
        """
        repoInfos = []
        for cid in DataCleaner.getUniqueCids(companyDf):
            DataCleaner.getRepoInfoByCid(companyDf, cid)
        
    @staticmethod
    def getRepoInfoDfByCid(companyDf, cid, ignoreNonUser = False):
        """
            
        """
        try:
            df = DataTools.loadCSVFromOutput(str(int(cid)))
        except pd.errors.EmptyDataError:
            columns = ['Full Name','Forks','Stars','Watchers','Commits','Branches','Contributors','Open Issues','PullRequests','YearCreated']
            df = pd.DataFrame(columns=columns)
            return df

        df = df.fillna(0)
        if ignoreNonUser:
            companies = DataCleaner.getCompaniesFromCid(companyDf, cid)
            usernames = Extractor.getUsernamesFromCompanies(companies)
            df = df[df['Full Name'].str.contains('|'.join(usernames))]
        return df

    @staticmethod
    def getRepoInfoByCid(companyDf, cid):
        """
            gets the repo info for the given cid and saves it to a csv file 
        """
        # check if csv exists, if it does, return
        if DataTools.isCSVExist(str(int(cid))):
            print("CSV already exists for cid: " + str(cid))
            return
        
        repoInfos = []
        # check if unfinished csv exists, if it does, load it and continue
        if DataCleaner.isUnfinished(cid):
            print("Unfinished work exists for cid: " + str(cid))
            with open('unfinished' + str(int(cid)), 'rb') as handle:
                    repoInfos = pickle.load(handle)
        

        companies = DataCleaner.getCompaniesFromCid(companyDf, cid)
        repos = Extractor.getRepoFromCompanies(companies, ignoreNonUser=False)
        
        # start from where we left off
        repos = repos[len(repoInfos):]
        for repo in tqdm(repos, desc="Getting repo info for cid: " + str(cid)):
            try:
                repoInfos.append(DataCleaner.getRepoInfoFromRepo(repo))
            except RateLimitExceededException:
                # save the current repoInfos a pickle file
                print('Dumping unfinished repos for cid: ' + str(cid))
                with open('unfinished' + str(int(cid)), 'wb') as handle:
                    pickle.dump(repoInfos, handle, protocol=pickle.HIGHEST_PROTOCOL)
                raise
            except ConnectTimeout:
                print('Dumping unfinished repos for cid: ' + str(cid))
                with open('unfinished' + str(int(cid)), 'wb') as handle:
                    pickle.dump(repoInfos, handle, protocol=pickle.HIGHEST_PROTOCOL)
                raise
            except ReadTimeout:
                print('Dumping unfinished repos for cid: ' + str(cid))
                with open('unfinished' + str(int(cid)), 'wb') as handle:
                    pickle.dump(repoInfos, handle, protocol=pickle.HIGHEST_PROTOCOL)
                raise

        df = pd.DataFrame(repoInfos)

        DataTools.saveDfInCSV(df, str(int(cid)))
    
    @staticmethod
    def isUnfinished(cid):
        return os.path.exists('unfinished' + str(int(cid)))
    
    @staticmethod
    def getRepoInfoFromRepo(repo):
        """
            Returns the total number of forks, stars, watchers, commits, branches, contributors, open issues, pull requests, and year created of repo 
        """
        
        repo._requester = DataTools.getGithub().getRequester()
        try:
            commits = repo.get_commits().totalCount
        except RateLimitExceededException:
            # print the exception and raise it
            raise
        except GithubException:
            print("GithubException for repo: " + repo.full_name)
            commits = math.nan
        except KeyError:
            print("KeyError for repo: " + repo.full_name)
            commits = math.nan

        try:
            branches = repo.get_branches().totalCount
        except RateLimitExceededException:
            raise 
        except GithubException:
            print("GithubException for repo: " + repo.full_name)
            branches = math.nan
        except KeyError:
            print("KeyError for repo: " + repo.full_name)
            branches = math.nan

        try:
            contributors = repo.get_contributors().totalCount
        except RateLimitExceededException:
            raise 
        except GithubException:
            print("GithubException for repo: " + repo.full_name)
            contributors = math.nan
        except KeyError:
            print("KeyError for repo: " + repo.full_name)
            contributors = math.nan

        try:
            pullRequests = repo.get_pulls().totalCount
        except RateLimitExceededException:
            raise 
        except GithubException:
            print("GithubException for repo: " + repo.full_name)
            pullRequests = math.nan
        except KeyError:
            print("KeyError for repo: " + repo.full_name)
            pullRequests = math.nan

        return {"Full Name": repo.full_name ,"Forks": repo.forks_count, "Stars": repo.stargazers_count, "Watchers": repo.watchers_count, "Commits": commits, "Branches": branches, "Contributors": contributors, "Open Issues": repo.open_issues_count, "PullRequests": pullRequests, "YearCreated": repo.created_at.year}
