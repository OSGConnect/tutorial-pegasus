#!/usr/bin/env python3

import logging
import os
import getpass
from pathlib import Path

from Pegasus.api import *


class WordfreqWorkflow:

    TOP_DIR = Path(__file__).parent.resolve()
    WORK_DIR = Path.home() / "workflows"


    def __init__(self):
        """."""
        self.runs_dir = self.WORK_DIR / "runs"
        self.scratch_dir = self.WORK_DIR / "scratch"
        self.output_dir = self.WORK_DIR / "outputs"

        self.props = Properties()

        self.wf = Workflow("wordfreq")
        self.tc = TransformationCatalog()
        self.sc = SiteCatalog()
        self.rc = ReplicaCatalog()

        self.wf.add_transformation_catalog(self.tc)
        self.wf.add_site_catalog(self.sc)
        self.wf.add_replica_catalog(self.rc)


    def generate_props(self):
        # simple condor-io file stageing
        self.props["pegasus.data.configuration"] = "condorio"

        # Provide a full kickstart record, including the environment, even for successful jobs
        self.props["pegasus.gridstart.arguments"] = "-f"

        # Limit the number of idle jobs for large workflows
        self.props["dagman.maxidle"] = "1000"

        # Help Pegasus developers by sharing performance data (optional)
        self.props["pegasus.monitord.encoding"] = "json"
        self.props["pegasus.catalog.workflow.amqp.url"] = "amqp://friend:donatedata@msgs.pegasus.isi.edu:5672/prod/workflows"

        # nicer looking submit dirs
        self.props["pegasus.dir.useTimestamp"] = "true"

        self.props.write()


    def generate_site_catalog(self):

        username = getpass.getuser()

        local = (
            Site("local")
            .add_directories(
                Directory(
                    Directory.SHARED_STORAGE, self.output_dir
                ).add_file_servers(
                    FileServer(f"file://{self.output_dir}", Operation.ALL)
                )
            )
            .add_directories(
                Directory(
                    Directory.SHARED_SCRATCH, self.scratch_dir
                ).add_file_servers(
                    FileServer(f"file://{self.scratch_dir}", Operation.ALL)
                )
            )
        )

        condorpool = (
            Site("condorpool")
            .add_pegasus_profile(style="condor")
            .add_condor_profile(
                universe="vanilla",
                requirements="HAS_SINGULARITY == True",
                request_cpus=1,
                request_memory="1 GB",
                request_disk="1 GB",
             )
            .add_profiles(
                Namespace.CONDOR, 
                key="+SingularityImage", 
                value='"/cvmfs/singularity.opensciencegrid.org/htc/rocky:9"'
            )
        )

        self.sc.add_sites(local, condorpool)


    def generate_transformation_catalog(self):

        wordfreq = Transformation(
                    name="wordfreq",
                    site="local",
                    pfn=self.TOP_DIR / "bin/wordfreq",
                    is_stageable=True
                ).add_pegasus_profile(clusters_size=1)
        
        summarize = Transformation(
                        name="summarize",
                        site="local",
                        pfn=self.TOP_DIR / "bin/summarize",
                        is_stageable=True
                    )
        
        self.tc.add_transformations(wordfreq, summarize)
        

    def generate_replica_catalog(self):

        input_files = [File(f.name) for f in (self.TOP_DIR / "inputs").iterdir() if f.name.endswith(".txt")]

        for f in input_files:
            self.rc.add_replica(site="local", lfn=f, pfn=self.TOP_DIR / "inputs" / f.lfn)


    def generate_workflow(self):

        # last job, child of all others
        summarize_job = (
            Job("summarize")
            .add_outputs(File("summary.txt"))
        )
        self.wf.add_jobs(summarize_job)
        
        input_files = [File(f.name) for f in (self.TOP_DIR / "inputs").iterdir() if f.name.endswith(".txt")]

        for f in input_files:
            out_file = File(f.lfn + ".out")
            wordfreq_job = (
                Job("wordfreq")
                .add_args(f, out_file)
                .add_inputs(f)
                .add_outputs(out_file)
            )
            
            self.wf.add_jobs(wordfreq_job)

            # establish the relationship between the jobs
            summarize_job.add_inputs(out_file)


    def plan_workflow(self):
        try:
            self.wf.plan(
                dir=self.runs_dir,
                sites=["condorpool"],
                output_sites=["local"],
                cluster=["horizontal"]
            )
        except PegasusClientError as e:
            print(e.output)


    def __call__(self):
        self.generate_props()
        self.generate_transformation_catalog()
        self.generate_site_catalog()
        self.generate_replica_catalog()
        self.generate_workflow()
        self.plan_workflow()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    wf = WordfreqWorkflow()
    wf()



