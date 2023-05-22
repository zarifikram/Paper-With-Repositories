import math
import os
import time
import pickle
from typing import List
import numpy as np
import pandas as pd
from requests import ConnectTimeout, ReadTimeout
from urllib3 import HTTPSConnectionPool
from Extractor import Extractor
from tqdm import tqdm 
from github import Repository
from DataTools import DataTools
from github.GithubException import GithubException, RateLimitExceededException
from RepoTools import RepoTools
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

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
         
        repoInfoByCid = DataTools.loadCSVFromOutput('repoList')
        finalDf = DataCleaner.getMatchingPaperInfoByCid(companyDf, repoInfoByCid)
        
        # finalDf = pd.concat(dfs, ignore_index=True)
        # finalDf = finalDf.drop_duplicates(['Title'])
        finalDf.drop(columns=['lowerTitle', 'stargazers_count', 'forks', 'open_issues_count', 'Watchers'], inplace=True)
        return finalDf
    
    @staticmethod
    def getMatchingPaperInfoByCid(companyDf, repoInfoByCid):
        """
            Returns a df with all the matched papers info for the given cid
            args:
                companyDf: the companyDf
                companies: the companies to get the matched papers for
                repoInfoByCid: the repoInfoByCid contains the repo info collected so far
        """

        # all the papers we extracted from github
        paperFromCompanyRepos = Extractor.loadCSVFromOutput(['allPapersCollectedDup'])
        companyDf['lowerTitle'] = companyDf.Title.str.lower()


        dfs = []
        for cid in tqdm(DataCleaner.getUniqueCids(companyDf)):
            companyDfFromCid = companyDf[companyDf.CID == cid].reset_index(drop = True)
            usernames = DataCleaner.getUsernamesFromCid(companyDf, cid)
            paperFromCompanyReposByCid = paperFromCompanyRepos[paperFromCompanyRepos.repo_link.str.contains('|'.join(usernames))].reset_index(drop = True)
            if len(paperFromCompanyReposByCid) == 0 or len(companyDfFromCid) == 0:
                continue
            try: 
                dfs.append(DataCleaner.join_dataframes_by_cosine_similarity(companyDfFromCid, paperFromCompanyReposByCid, 'lowerTitle', 'lowerTitle', 0.8))
            except ValueError:
                continue
        matchedPapersDf = DataCleaner.join_dataframes_by_cosine_similarity(companyDf, paperFromCompanyRepos, 'lowerTitle', 'lowerTitle', 0.8)
        dfs.append(matchedPapersDf)

        matchedPapersDf = pd.concat(dfs, ignore_index=True)
        # need to join matchedPaperDf with cid repos
        repoInfoByCid['repo_link'] = 'https://github.com/' + repoInfoByCid['Full Name']
        # print(matchedPapersDf)
        merged_data = matchedPapersDf.merge(repoInfoByCid, how='left', on = 'repo_link')
 
        # merged_data = merged_data.drop_duplicates(['Title'])
        return merged_data
    
    @staticmethod
    def preprocess_data(data):
    # Lowercase and strip the strings
        return data.str.lower().str.strip()

    @staticmethod
    def join_dataframes_by_cosine_similarity(df1, df2, column1, column2, threshold, batch_size=1000):
        # Preprocess the column data
        df1[column1] = DataCleaner.preprocess_data(df1[column1])
        df2[column2] = DataCleaner.preprocess_data(df2[column2])

        # Create TF-IDF vectorizer
        vectorizer = TfidfVectorizer()

        # Create a list to store the matched batch dataframes
        matched_dfs = []

        # Process the data in batches
        for i in tqdm(range(0, len(df1), batch_size)):
            # Get the current batch of data
            df1_batch = df1.iloc[i:i+batch_size]
            
            # Fit and transform the data for the current batch
            tfidf_matrix1 = vectorizer.fit_transform(df1_batch[column1])
            try:
                tfidf_matrix2 = vectorizer.transform(df2[column2])
            except ValueError:
                print(df2[column2])
                raise

            # Compute cosine similarity for the current batch
            similarity_matrix = cosine_similarity(tfidf_matrix1, tfidf_matrix2)

            # Find matches for the current batch
            batch_matches = []
            for i, row in df1_batch.iterrows():
                matches = similarity_matrix[i % batch_size] >= threshold
                if matches.any():
                    matched_df = df2[matches].copy()
                    matched_df['lowerTitle'] = row[column1]
                    matched_dfs.append(matched_df)

        # Concatenate the matched batch dataframes into a single dataframe
        joined_df = pd.concat(matched_dfs)

        joined_df = joined_df.merge(df1, how='left', on = 'lowerTitle')
        return joined_df

    @staticmethod
    def getUsernamesFromCid(companyDf, cid):
        companies = DataCleaner.getCompaniesFromCid(companyDf, cid)
        usernames = []
        for company in companies:
            usernames.extend(Extractor.getUsernamesFromCompanies(companies))
        
        return usernames
    
    @staticmethod
    def getInfoDfFromCidAndYear(companyDf):
        cids = DataCleaner.getUniqueCids(companyDf)
        years = DataCleaner.getUniqueYears(companyDf)
        dfs = []
        matchedPapersDf = DataTools.loadCSVFromOutput('finalStuff/matched_papersV3')
        for cid in tqdm(cids):
            df = DataCleaner.analyzeByCid(companyDf, matchedPapersDf, cid, years)
            dfs.append(df)
        
        finalDf = pd.concat(dfs)
        return finalDf

    @staticmethod
    def analyzeByCid(companyDf, matchedPapersDf, cid, years):
        """
            Analyzes the given cid for the given years
        """
        cidYearDicts = []
        dfByCid = DataCleaner.getDfByCidAndYear(companyDf, cid)
        repoInfoByCid = DataCleaner.getRepoInfoDfByCid(companyDf, cid, ignoreNonUser = True)

        matchedPapersDfByCid = DataCleaner.getMatchedPaperByCid(cid, matchedPapersDf)
        for year in years:
            nMatchPapersByCidInYear = DataCleaner.getNumberOfRowsByYear(matchedPapersDfByCid, year)
            repoTotalInfoinYear = DataCleaner.getRepoInfoInYear(repoInfoByCid, year)
            
            matchedRepoTotalInfoinYear = DataCleaner.getRepoInfoFromMatchedPapersDf(matchedPapersDfByCid, year)
            nPapersInTheYear = DataCleaner.getNumberOfRowsByYear(dfByCid, year)
            cidYearDict = {"CID": cid, "Year": year, "MatchedPapers": nMatchPapersByCidInYear, "TotalPapers": nPapersInTheYear}
            cidYearDict.update(repoTotalInfoinYear)
            cidYearDict.update(matchedRepoTotalInfoinYear)
            cidYearDicts.append(cidYearDict)
        return pd.DataFrame(cidYearDicts)

    @staticmethod
    def getMatchedPaperByCid(cid, matchedPaperDf):
        return matchedPaperDf[matchedPaperDf.CID == cid]
    
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
    def getRepoInfoFromMatchedPapersDf(df, year):
        df = df[df.YearCreated == year]
        matchedRepoInfo = {
            'Matched Forks' : df.Forks.sum(), 
            'Matched Stars' : df.Stars.sum(),
            'Matched Commits': df.Commits.sum(), 
            'Matched Branches': df.Branches.sum(),
            'Matched Contributors': df.Contributors.sum(), 
            'Matched Open Issues':  df['Open Issues'].sum(), 
            'Matched PullRequests': df.PullRequests.sum(),
            'Matched Repos Created': len(df)
        }
        return matchedRepoInfo
    
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

    @staticmethod
    def appendRepoInfoByUsername(companyDf, username, company):
        cid = DataCleaner.getCidFromCompany(companyDf, company)
        filename = username + "RepoWithReadmes"
        extendedData = RepoTools.loadPickle('extended_' + filename)
        repos = [_['repo'] for _ in extendedData]
        repoInfos = []
        for repo in tqdm(repos):
            repoInfos.append(DataCleaner.getRepoInfoFromRepo(repo))
        
        df = pd.DataFrame(repoInfos)
        dfOld = DataTools.loadCSVFromOutput(str(int(cid)))
        df = pd.concat([dfOld, df], ignore_index=True)
        DataTools.saveDfInCSV(df, str(int(cid)))
    
    @staticmethod
    def getRepoInfoAllCID(companyDf):
        cids = DataCleaner.getUniqueCids(companyDf=companyDf)
        dfs = []
        for cid in tqdm(cids):
            try:
                repoInfoDf = DataTools.loadCSVFromOutput(str(int(cid)))
            except pd.errors.EmptyDataError:
                columns = ['Full Name','Forks','Stars','Watchers','Commits','Branches','Contributors','Open Issues','PullRequests','YearCreated']
                repoInfoDf = pd.DataFrame(columns=columns)

            dfs.append(repoInfoDf)

        bigDf = pd.concat(dfs, ignore_index=True)
        bigDf.drop_duplicates(['Full Name'])
        bigDf.fillna(0)
        DataTools.saveDfInCSV(bigDf, 'repoList')
    