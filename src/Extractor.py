import json
import os
from RepoTools import RepoTools
import pandas as pd

class Extractor:
    @staticmethod
    def extractFromConfig():
        """
        Extracts the configuration from the config file
        """
        # get the config file from json
        config = Extractor.getConfig()

        # for each company in config, fetch all repo df
        for companyToRepos in config:
            Extractor.getCompanyDF(companyToRepos)
            

    @staticmethod
    def getConfig():
        """
        Returns the configuration from json file
        """
        # get the config file from json
        with open('CompanyTORepos.json') as json_file:
            data = json.load(json_file)
        return data
        
    @staticmethod
    def getCompanyDF(companyToRepos):
        """
        Returns the repo df for the given company
        """
        companyName = companyToRepos["company"]
        repos = companyToRepos["repos"]

        # if already exists, return
        companyCSVFileName = companyName + ".csv"
        if os.path.exists(os.path.join(os.curdir, "../finalOutputs", companyCSVFileName)):
            print(f"Already exists for {companyName}, ignoring...")
            return 
        
        # if no repos, return
        if len(repos) == 0:
            return
        
        repoDFs = []
        for repo in repos:
            repoDF = Extractor.getRepoDFromUsername(repo)
            repoDFs.append(repoDF)

        companyDf = pd.concat(repoDFs)
        Extractor.saveDfInCSV(companyDf, companyName)


    @staticmethod
    def saveDfInCSV(df, company):
        outputPath = os.path.join(os.curdir, "../finalOutputs")  
        if not os.path.exists(outputPath):
            os.mkdir(outputPath)
        df.to_csv(os.path.join(outputPath, f"{company}.csv"), index = False)

    @staticmethod
    def loadCSVFromOutput(company):
        outputPath = os.path.join(os.curdir, "../finalOutputs")  
        return pd.read_csv(os.path.join(outputPath, f"{company}.csv"))



    @staticmethod
    def getRepoDFromUsername(username):
        """
            Returns the repo df for the given username
        """
        # if repoDataWithReadme not present, start from scratch
        filename = username + "RepoWithReadmes"

        if os.path.exists(os.path.join(os.curdir, "../pickles", filename)):
            if os.path.exists(os.path.join(os.curdir, "../pickles", 'extended_' + filename)):
                extendedData = RepoTools.loadPickle('extended_' + filename)
            else:
                extendedData = RepoTools.loadReposWithReadmeAndGetExtendedData(username, saveExtendedRepoWithReadme=True)
        else:
            extendedData = RepoTools.savePaperNameFromGithubUser(username, saveRepoWithReadme=True, saveExtendedRepoWithReadme=True)

        return RepoTools.getPaperDfFromExtendedRepoWithReadmesAndData(extendedData, ignoreArxivIfPaperTitleExists = False)