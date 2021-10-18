[title]: - "Use Pegasus to Manage Workflows on OSG Connect"
[TOC]


## Introduction

[The Pegasus project](https://pegasus.isi.edu) encompasses a set of technologies that help workflow-based applications execute in a number of different environments including desktops, campus clusters, grids, and clouds. Pegasus bridges the scientific domain and the execution environment by automatically mapping high-level workflow descriptions onto distributed resources. It automatically locates the necessary input data and computational resources necessary for workflow execution. Pegasus enables scientists to construct workflows in abstract terms without worrying about the details of the underlying execution environment or the particulars of the low-level specifications required by the middleware. Some of the advantages of using Pegasus include:

   * **Portability / Reuse** - User created workflows can easily be run in different environments without alteration. Pegasus currently runs workflows on top of Condor, Grid infrastrucutures such as Open Science Grid and XSEDE, Amazon EC2, Google Cloud, and many campus clusters. The same workflow can run on a single system or across a heterogeneous set of resources.

   * **Performance** - The Pegasus mapper can reorder, group, and prioritize tasks in order to increase the overall workflow performance.

   * **Scalability** - Pegasus can easily scale both the size of the workflow, and the resources that the workflow is distributed over. Pegasus runs workflows ranging from just a few computational tasks up to 1 million tasks. The number of resources involved in executing a workflow can scale as needed without any impediments to performance.

   * **Provenance** - By default, all jobs in Pegasus are launched via the kickstart process that captures runtime provenance of the job and helps in debugging. The provenance data is collected in a database, and the data can be summarized with tools such as pegasus-statistics or directly with SQL queries.

   * **Data Management** - Pegasus handles replica selection, data transfers and output registrations in data catalogs. These tasks are added to a workflow as auxiliary jobs by the Pegasus planner.

   * **Reliability** - Jobs and data transfers are automatically retried in case of failures. Debugging tools such as pegasus-analyzer help the user to debug the workflow in case of non-recoverable failures.

   * **Error Recovery** - When errors occur, Pegasus tries to recover when possible by retrying tasks, retrying the entire workflow, providing workflow-level checkpointing, re-mapping portions of the workflow, trying alternative data sources for staging data, and, when all else fails, providing a rescue workflow containing a description of only the work that remains to be done. Pegasus keeps track of what has been done (provenance) including the locations of data used and produced, and which software was used with which parameters.

As mentioned earlier in this book, OSG has no read/write enabled shared file system across the resources. Jobs are required to either bring inputs along with the job, or as part of the job stage the inputs from a remote location. The following examples highlight how Pegasus can be used to manage workloads in such an environment by providing an abstraction layer around things like data movements and job retries, enabling the users to run larger workloads, spending less time developing job management tools and babysitting their computations.

Pegasus workflows have 4 components:

  1. **Site Catalog** - Describes the execution environment in which the workflow
    will be executed.
  2. **Transformation Catalog** - Specifies locations of the executables used by
    the workflow.
  3. **Replica Catalog** - Specifies locations of the input data to the workflow.
  4. **Workflow Description** - An abstract workflow description containing compute
    steps and dependencies between the steps. We refer to this workflow as abstract
    because it does not contain data locations and available software.

When developing a Pegasus Workflow using the
[Python API](https://pegasus.isi.edu/documentation/reference-guide/api-reference.html),
all four components may be defined in the same file.  

For details, please refer to the [Pegasus documentation](https://pegasus.isi.edu/documentation/).

## wordfreq workflow

![fig 1](https://raw.githubusercontent.com/OSGConnect/tutorial-pegasus/master/workflow.png)

`wordfreq` is an example application and workflow that can be used to introduce
Pegasus tools and concepts.

The application is available on the OSG Connect
login host.

This example is using [OSG StashCache](https://derekweitzel.com/2018/09/26/stashcache-by-the-numbers/)
for data transfers. Credentials are transparant to the end users, so all the
workflow has to do is use the `stashcp` command to copy data to and from the OSG
Connect Stash instance.

Additionally, this example uses a custom container to run jobs. The container
capability is provided by OSG ([Docker and Singularity Containers](https://support.opensciencegrid.org/support/solutions/articles/12000024676-docker-and-singularity-containers)) and
is used by setting HTCondor properties when defining your workflow.  

**Exercise 1**: create a copy of the Pegasus tutorial and change the working
directory to the wordfreq workflow by running the following commands:

	$ tutorial pegasus
	$ cd tutorial-pegasus/wordfreq

In the `wordfreq` directory, you will find:

    wordfreq/
    ├── bin
    |   ├── summarize
    |   └── wordfreq
    ├── inputs
    |   ├── Alices_Adventures_in_Wonderland_by_Lewis_Carroll.txt
    |   ├── Dracula_by_Bram_Stoker.txt
    |   ├── Pride_and_Prejudice_by_Jane_Austen.txt
    |   ├── The_Adventures_of_Huckleberry_Finn_by_Mark_Twain.txt
    |   ├── Ulysses_by_James_Joyce.txt
    |   └── Visual_Signaling_By_Signal_Corps_United_States_Army.txt
    ├── many-more-inputs
    |   └── ...
    └── workflow.py

The `inputs/` directory contains 6 public domain ebooks. The wordreq workflow uses the
two executables in the `bin/` directory. `bin/wordfreq` takes a text file as input
and produces a summary output file containting the counts and names of the top five
most frequently used words from the input file. A *wordfreq* job is created for
each file in `inputs/`. `bin/summarize` concatenates the
the output of each `wordfreq` job into a single output file called `summary.txt`.

This workflow structure, which is a set of independent tasks joining into a single summary
or analysis type of task, is a common use case on OSG and therefore this workflow
can be thought of as a template for such problems. For example, instead of using
wordfreq on ebooks, the application could be protein folding on a set of input
structures.

When invoked, the workflow script (`workflow.py`) does the following:

  1. Writes the file `pegasus.properties`. This file contains configuration settings
     used by Pegasus and HTCondor.

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

  2. Writes the file `sites.yml`. This file describes the execution environment in
     which the workflow will be run.

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


In order for the workflow to use the container capability provided by OSG,
([Docker and Singularity Containers](https://support.opensciencegrid.org/support/solutions/articles/12000024676-docker-and-singularity-containers))
the following HTCondor profiles must be
added to the condorpool execution site: `requirements="HAS_SINGULARITY == True"`,
and `+SingularityImage='"/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo-el7:latest"'`.
The `requirements` expression indicates that the host on which the jobs run
must have Singularity installed. `+SingularityImage` specifies the container to use.

If you want to use stashcp, make sure it is accessible in the image. A symlink
to `/cvmfs/` from a standard location in the PATH is often enough for the
tool to be found and used ([example Dockerfile](https://github.com/pegasus-isi/osg-container-images/blob/master/osg-el7/Dockerfile)).

  3. Writes the file `transformations.yml`. This file specifies the executables used
     in the workflow and contains the locations where they are physically located.
     In this example, we have two entries: `wordfreq` and `summarize`.

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


  4. Writes the file `replicas.yml`. This file specifies the physical locations of
     any input files used by the workflow. In this example, there is an entry for
     each file in the `inputs/` directory.

         # --- Replicas -----------------------------------------------------------------
         input_files = [File(f.name) for f in (TOP_DIR / "inputs").iterdir() if f.name.endswith(".txt")]

         rc = ReplicaCatalog()
         for f in input_files:
             rc.add_replica(site="local", lfn=f, pfn=TOP_DIR / "inputs" / f.lfn)

         # write ReplicaCatalog to replicas.yml
         rc.write()

  5. Builds the wordfreq workflow and submits it for execution. When `wf.plan` is
     invoked, `pegasus.properties`, `sites.yml`, `transformations.yml`, and
    `replicas.yml` will be consumed as part of the workflow planning process. Note that
    in this step there is no mention of data movement and job details as these are
    added by Pegasus when the workflow is planned into an executable workflow. As
    part of the planning process, additional jobs which handle scratch directory
    creation, data staging, and data cleanup are added to the workflow.

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
              staging_sites={"condorpool": "stash"},
              output_sites=["local"],
              cluster=["horizontal"],
              submit=True
          )

**Exercise 2:** Submit the workflow by executing `workflow.py`.

    $ ./workflow.py

Note that when Pegasus plans/submits a workflow, a workflow directory is created
and presented in the output. In the following example output, the workflow directory
is `/home/ryantanaka/workflows/runs/ryantanaka/pegasus/wordfreq-workflow/run0014`.

    2020.12.18 14:33:07.059 CST:   -----------------------------------------------------------------------
    2020.12.18 14:33:07.064 CST:   File for submitting this DAG to HTCondor           : wordfreq-workflow-0.dag.condor.sub
    2020.12.18 14:33:07.070 CST:   Log of DAGMan debugging messages                 : wordfreq-workflow-0.dag.dagman.out
    2020.12.18 14:33:07.075 CST:   Log of HTCondor library output                     : wordfreq-workflow-0.dag.lib.out
    2020.12.18 14:33:07.080 CST:   Log of HTCondor library error messages             : wordfreq-workflow-0.dag.lib.err
    2020.12.18 14:33:07.086 CST:   Log of the life of condor_dagman itself          : wordfreq-workflow-0.dag.dagman.log
    2020.12.18 14:33:07.091 CST:
    2020.12.18 14:33:07.096 CST:   -no_submit given, not submitting DAG to HTCondor.  You can do this with:
    2020.12.18 14:33:07.107 CST:   -----------------------------------------------------------------------
    2020.12.18 14:33:10.381 CST:   Your database is compatible with Pegasus version: 5.1.0dev
    2020.12.18 14:33:11.347 CST:   Created Pegasus database in: sqlite:////home/ryantanaka/workflows/runs/ryantanaka/pegasus/wordfreq-workflow/run0014/wordfreq-workflow-0.replicas.db
    2020.12.18 14:33:11.352 CST:   Your database is compatible with Pegasus version: 5.1.0dev
    2020.12.18 14:33:11.404 CST:   Output replica catalog set to jdbc:sqlite:/home/ryantanaka/workflows/runs/ryantanaka/pegasus/wordfreq-workflow/run0014/wordfreq-workflow-0.replicas.db
    [WARNING]  Submitting to condor wordfreq-workflow-0.dag.condor.sub
    2020.12.18 14:33:12.060 CST:   Time taken to execute is 5.818 seconds

    Your workflow has been started and is running in the base directory:

    /home/ryantanaka/workflows/runs/ryantanaka/pegasus/wordfreq-workflow/run0014

    *** To monitor the workflow you can run ***

    pegasus-status -l /home/ryantanaka/workflows/runs/ryantanaka/pegasus/wordfreq-workflow/run0014


    *** To remove your workflow run ***

    pegasus-remove /home/ryantanaka/workflows/runs/ryantanaka/pegasus/wordfreq-workflow/run0014

This directory is the handle to the workflow instance
and is used by Pegasus command line tools. Some useful tools to know about:

* `pegasus-status -v [wfdir]`
     Provides status on a currently running workflow. ([more](https://pegasus.isi.edu/documentation/manpages/pegasus-status.html))
* `pegasus-analyzer [wfdir]`
     Provides debugging clues why a workflow failed. Run this after a workflow has failed. ([more](https://pegasus.isi.edu/documentation/manpages/pegasus-analyzer.html))
* `pegasus-statistics [wfdir]`
     Provides statistics, such as walltimes, on a workflow after it has completed. ([more](https://pegasus.isi.edu/documentation/manpages/pegasus-statistics.html))
* `pegasus-remove [wfdir]`
     Removes a workflow from the system. ([more](https://pegasus.isi.edu/documentation/manpages/pegasus-remove.html))

**Exercise 3:** Check the status of the workflow:

	$ pegasus-status [wfdir]

You can keep checking the status periodically to see that the workflow is making progress.

**Exercise 4:** Examine a submit file and the `*.dag.dagman.out` files. Do these
look familiar to you from previous modules in the book? Pegasus is based on
HTCondor and DAGMan.

	$ cd [wfdir]
	$ cat 00/00/summarize_ID0000001.sub
	...
	$ cat *.dag.dagman.out
	...

**Exercise 5:** Keep checking progress with `pegasus-status`. Once the workflow
is done, display statistics with `pegasus-statistics`:

	$ pegasus-status [wfdir]
	$ pegasus-statistics [wfdir]
	...

**Exercise 6:** `cd` to the output directory and look at the outputs. Which is
the most common word used in the 6 books? Hint:

	$ cd $HOME/workflows/outputs
	$ head -n 5 *.out

**Exercise 7:** Want to try something larger? Copy the additional 994 ebooks from \
the many-more-inputs/ directory to the inputs/ directory:

	$ cp many-more-inputs/* inputs/

As these tasks are really short, let's tell Pegasus to cluster multiple tasks
together into jobs. If you do not do this step, the jobs will still run, but not
very efficiently. This is because every job has a small scheduling overhead. For
short jobs, the overhead is obvious. If we make the jobs longer, the scheduling
overhead becomes negligible. To enable the clustering feature, edit the
`workflow.py` script. Find the section under `Transformations`:

    wordfreq = Transformation(
                name="wordfreq",
                site="local",
                pfn=TOP_DIR / "bin/wordfreq",
                is_stageable=True,
                arch=Arch.X86_64
            ).add_pegasus_profile(clusters_size=1)

Change `clusters_size=1` to `clusters_size=50`.

This informs Pegasus that it is ok to cluster up to 50 of the jobs which use the
wordfreq executable. Save the file and re-run the script:

    $ ./workflow.py

Use `pegasus-status` and `pegasus-statistics` to monitor your workflow. Using
`pegasus-statistics`, determine how many jobs ended up in your workflow and see
how this compares with our initial workflow run.

## Getting Help

For assistance or questions, please email the OSG User Support team  at
[support@opensciencegrid.org](mailto:support@opensciencegrid.org) or visit the [help desk and community forums](https://support.opensciencegrid.org).
