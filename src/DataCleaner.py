import os
import pandas as pd
from Extractor import Extractor
from tqdm import tqdm 

class DataCleaner:
    """
        Responsible for making a CSV file for each cid with year with the number of matched repos
        Also makes a CSV file for each cid with matched papers along with all the info
    """

    
    companyToRepos = Extractor.getConfig()

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
        matchedPapersDf = DataCleaner.getMatchedPapers(dfByCid, paperFromCompanyRepos)
        repos = Extractor.getRepoFromCompanies(companies)
        for year in years:
            nMatchPapersByCidInYear = DataCleaner.getNumberOfRowsByYear(matchedPapersDf, year)
            nReposCreatedInTheYear = DataCleaner.nReposCreatedInTheYear(repos, year)
            nPapersInTheYear = DataCleaner.getNumberOfRowsByYear(dfByCid, year)
            cidYearDicts.append({"CID": cid, "Year": year, "MatchedPapers": nMatchPapersByCidInYear, "ReposCreated": nReposCreatedInTheYear, "TotalPapers": nPapersInTheYear})
        return pd.DataFrame(cidYearDicts)

    
    @staticmethod
    def nReposCreatedInTheYear(repos, year):
        """
            Returns the number of repos in the given year
        """
        return len([repo for repo in repos if repo.created_at.year == year])
    
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