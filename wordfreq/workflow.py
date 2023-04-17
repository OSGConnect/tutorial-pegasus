#!/usr/bin/env python3
import logging
import os
import getpass
from pathlib import Path

from Pegasus.api import *

logging.basicConfig(level=logging.INFO)

# --- Working Directory Setup --------------------------------------------------
# A good working directory for workflow runs and output files
WORK_DIR = Path.home() / "workflows"
WORK_DIR.mkdir(exist_ok=True)

TOP_DIR = Path(__file__).resolve().parent

# --- Properties ---------------------------------------------------------------
props = Properties()
props["pegasus.data.configuration"] = "nonsharedfs"

# Provide a full kickstart record, including the environment, even for successful jobs
props["pegasus.gridstart.arguments"] = "-f"

#Limit the number of idle jobs for large workflows
props["dagman.maxidle"] = "1000"

# Help Pegasus developers by sharing performance data (optional)
props["pegasus.monitord.encoding"] = "json"
props["pegasus.catalog.workflow.amqp.url"] = "amqp://friend:donatedata@msgs.pegasus.isi.edu:5672/prod/workflows"

# write properties file to ./pegasus.properties
props.write()

# --- Sites --------------------------------------------------------------------
sc = SiteCatalog()

# local site (submit machine)
local_site = Site(name="local", arch=Arch.X86_64)

local_shared_scratch = Directory(directory_type=Directory.SHARED_SCRATCH, path=WORK_DIR / "scratch")
local_shared_scratch.add_file_servers(FileServer(url="file://" + str(WORK_DIR / "scratch"), operation_type=Operation.ALL))
local_site.add_directories(local_shared_scratch)

local_storage = Directory(directory_type=Directory.LOCAL_STORAGE, path=WORK_DIR / "outputs")
local_storage.add_file_servers(FileServer(url="file://" + str(WORK_DIR / "outputs"), operation_type=Operation.ALL))
local_site.add_directories(local_storage)

local_site.add_env(PATH=os.environ["PATH"])
sc.add_sites(local_site)

# osdf site (staging site, where intermediate data will be stored)
osdf_site = Site(name="osdf", arch=Arch.X86_64, os_type=OS.LINUX)
# uw.osg-htc.org APs and osgconnect.org APs have differnet configs
if True:
    osdf_staging_path = "/mnt/stash/ospool/PROTECTED/{USER}/staging".format(USER=getpass.getuser())
    osdf_shared_scratch = Directory(directory_type=Directory.SHARED_SCRATCH, path=osdf_staging_path)
    osdf_shared_scratch.add_file_servers(
        FileServer(
            url="stash:///ospool/PROTECTED/{USER}/staging".format(USER=getpass.getuser()), 
            operation_type=Operation.ALL)
    )
    osdf_site.add_directories(osdf_shared_scratch)
else:
    osdf_site = Site(name="osdf", arch=Arch.X86_64, os_type=OS.LINUX)
    osdf_staging_path = "/public/{USER}/staging".format(USER=getpass.getuser())
    osdf_shared_scratch = Directory(directory_type=Directory.SHARED_SCRATCH, path=osdf_staging_path)
    osdf_shared_scratch.add_file_servers(
        FileServer(
            url="osdf:///osgconnect{STASH_STAGING_PATH}".format(STASH_STAGING_PATH=osdf_staging_path), 
            operation_type=Operation.ALL)
    )
    osdf_site.add_directories(osdf_shared_scratch)
sc.add_sites(osdf_site)

# condorpool (execution site)
condorpool_site = Site(name="condorpool", arch=Arch.X86_64, os_type=OS.LINUX)
condorpool_site.add_pegasus_profile(style="condor")
condorpool_site.add_condor_profile(
    universe="vanilla",
    requirements="HAS_SINGULARITY == True",
    request_cpus=1,
    request_memory="1 GB",
    request_disk="1 GB",
)
condorpool_site.add_profiles(
    Namespace.CONDOR, 
    key="+SingularityImage", 
    value='"/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo-el7:latest"'
)

sc.add_sites(condorpool_site)

# write SiteCatalog to ./sites.yml
sc.write()

# --- Transformations ----------------------------------------------------------
wordfreq = Transformation(
            name="wordfreq",
            site="local",
            pfn=TOP_DIR / "bin/wordfreq",
            is_stageable=True,
            arch=Arch.X86_64
        ).add_pegasus_profile(clusters_size=1)

summarize = Transformation(
                name="summarize",
                site="local",
                pfn=TOP_DIR / "bin/summarize",
                is_stageable=True,
                arch=Arch.X86_64
            )

tc = TransformationCatalog()
tc.add_transformations(wordfreq, summarize)

# write TransformationCatalog to ./transformations.yml
tc.write()

# --- Replicas -----------------------------------------------------------------
input_files = [File(f.name) for f in (TOP_DIR / "inputs").iterdir() if f.name.endswith(".txt")]

rc = ReplicaCatalog()
for f in input_files:
    rc.add_replica(site="local", lfn=f, pfn=TOP_DIR / "inputs" / f.lfn)

# write ReplicaCatalog to replicas.yml
rc.write()

# --- Workflow -----------------------------------------------------------------
wf = Workflow(name="wordfreq-workflow")

summarize_job = Job(summarize).add_outputs(File("summary.txt"))
wf.add_jobs(summarize_job)

for f in input_files:
    out_file = File(f.lfn + ".out")
    wordfreq_job = Job(wordfreq)\
                    .add_args(f, out_file)\
                    .add_inputs(f)\
                    .add_outputs(out_file)
    
    wf.add_jobs(wordfreq_job)

    summarize_job.add_inputs(out_file)

# plan and run the workflow
wf.plan(
    dir=WORK_DIR / "runs",
    sites=["condorpool"],
    staging_sites={"condorpool": "osdf"},
    output_sites=["local"],
    cluster=["horizontal"],
    submit=True
)
