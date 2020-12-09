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
props["pegasus.dir.storage.mapper"] = "Flat"
props["pegasus.dir.storage.deep"] = "True"
props["pegasus.condor.logs.symlink"] = "false"
props["pegasus.data.configuration"] = "nonsharedfs"

# Provide a full kickstart record, including the environment, even for successful jobs
props["pegasus.gridstart.arguments"] = "-f"

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

# stash site (staging site, where intermediate data will be stored)
stash_site = Site(name="stash", arch=Arch.X86_64, os_type=OS.LINUX)
stash_staging_path = "/public/{USER}/staging".format(USER=getpass.getuser())
stash_shared_scratch = Directory(directory_type=Directory.SHARED_SCRATCH, path=stash_staging_path)
stash_shared_scratch.add_file_servers(
    FileServer(
        url="stash:///osgconnect{STASH_STAGING_PATH}".format(STASH_STAGING_PATH=stash_staging_path), 
        operation_type=Operation.ALL)
)
stash_site.add_directories(stash_shared_scratch)
sc.add_sites(stash_site)

# condorpool (execution site)
condorpool_site = Site(name="condorpool", arch=Arch.X86_64, os_type=OS.LINUX)
condorpool_site.add_pegasus_profile(style="condor")
condorpool_site.add_condor_profile(
    universe="vanilla",
    requirements='OSGVO_OS_STRING == "RHEL 7" && HAS_MODULES == True',
    request_cpus=1,
    request_memory="1 GB",
    request_disk="1 GB",
)
condorpool_site.add_profiles(Namespace.CONDOR, key="+WantsStashCache", value=True)
sc.add_sites(condorpool_site)

# write SiteCatalog to ./sites.yml
sc.write()

# --- Transformations ----------------------------------------------------------
wordfreq = Transformation(
            name="wordfreq",
            site="local",
            pfn=TOP_DIR / "wordfreq",
            is_stageable=True,
            arch=Arch.X86_64
        ).add_pegasus_profile(clusters_size=1)

tc = TransformationCatalog()
tc.add_transformations(wordfreq)

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

for f in input_files:
    out_file = File(f.lfn + ".out")
    wordfreq_job = Job(wordfreq)\
                    .add_args(f, out_file)\
                    .add_inputs(f)\
                    .add_outputs(out_file)
    
    wf.add_jobs(wordfreq_job)

# plan and run the workflow
wf.plan(
    dir=WORK_DIR / "runs",
    sites=["condorpool"],
    staging_sites={"condorpool": "stash"},
    output_sites=["local"],
    cluster=["horizontal"],
    submit=True
)
