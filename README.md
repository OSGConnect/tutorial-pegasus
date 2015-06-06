# Use Pegasus to Manage wordfreq tasks

 * [Introduction](#introduction)
 * [wordfreq workflow](#wordfreq-workflow)
 * [Getting Help](#getting-help)


## Pegasus Workflow Management System

[The Pegasus project](https://pegasus.isi.edu) encompasses a set of technologies that help workflow-based applications execute in a number of different environments including desktops, campus clusters, grids, and clouds. Pegasus bridges the scientific domain and the execution environment by automatically mapping high-level workflow descriptions onto distributed resources. It automatically locates the necessary input data and computational resources necessary for workflow execution. Pegasus enables scientists to construct workflows in abstract terms without worrying about the details of the underlying execution environment or the particulars of the low-level specifications required by the middleware. Some of the advantages of using Pegasus include:

   * **Portability / Reuse** - User-created workflows can easily be run in different environments without alteration. Pegasus currently runs workflows on top of Condor, Grid infrastrucutures such as Open Science Grid and TeraGrid, Amazon EC2, Nimbus, and many campus clusters. The same workflow can run on a single system or across a heterogeneous set of resources.

   * **Performance** - The Pegasus mapper can reorder, group, and prioritize tasks in order to increase the overall workflow performance.

   * **Scalability** - Pegasus can easily scale both the size of the workflow, and the resources that the workflow is distributed over. Pegasus runs workflows ranging from just a few computational tasks up to 1 million tasks. The number of resources involved in executing a workflow can scale as needed without any impediments to performance.

   * **Provenance** - By default, all jobs in Pegasus are launched via the kickstart process that captures runtime provenance of the job and helps in debugging. The provenance data is collected in a database, and the data can be summaries with tools such as pegasus-statistics, pegasus-plots, or directly with SQL queries.

   * **Data Management** - Pegasus handles replica selection, data transfers and output registrations in data catalogs. These tasks are added to a workflow as auxiliary jobs by the Pegasus planner.

   * **Reliability** - Jobs and data transfers are automatically retried in case of failures. Debugging tools such as pegasus-analyzer help the user to debug the workflow in case of non-recoverable failures.

   * **Error Recovery** - When errors occur, Pegasus tries to recover when possible by retrying tasks, retrying the entire workflow, providing workflow-level checkpointing, re-mapping portions of the workflow, trying alternative data sources for staging data, and, when all else fails, providing a rescue workflow containing a description of only the work that remains to be done.

As mentioned earlier in this book, OSG has no read/write enabled shared file system across the resources. Jobs are required to either bring inputs along with the job, or as part of the job stage the inputs from a remote location. The following examples highlight how Pegasus can be used to manage workloads in such an environment by providing an abstraction layer around things like data movements and job retries, enabling the users to run larger workloads, spending less time developing job management tool and babysitting their computations.

Pegasus workflows have 4 components:

   * **DAX** - Abstract workflow description containing compute steps and dependencies between the steps. This is called abstract because it does not contain data locations and available software. The DAX format is XML, but it is most commonly generated via the provided APIS ([documentation](http://pegasus.isi.edu/documentation)). [Python](http://pegasus.isi.edu/wms/docs/latest/python/), [Java](http://pegasus.isi.edu/wms/docs/latest/javadoc/edu/isi/pegasus/planner/dax/ADAG.html) and [Perl](http://pegasus.isi.edu/wms/docs/latest/perl/) APIs are available. 
     
   * **Transformation Catalog** - Specifies locations of software used by the workflow
     
   * **Replica Catalog** - Specifies locations of input data
     
   * **Site Catalog** - Describes the execution environment

However, for simple workflows, the transformation and replica catalog can be contained inside the DAX, and to further simplify the setup, the following examples generate the site catalog on the fly. This means that the user really only has to be concerned about creating the DAX.  

For details, please refer to the [Pegasus documentation](http://pegasus.isi.edu/wms/docs/latest/).

## wordfreq workflow

`wordfreq` is an example application and workflow that can be used to introduce Pegasus tools and concepts. The application is available on the OSG Connect login host.

**Exercise 1**: create a copy of the Pegasus tutorial and change the working directory to the wordfreq workflow by running the following commands:
```
$ tutorial pegasus
$ cd tutorial-pegasus/wordfreq-workflow
```
In the wordfreq-workflow directory, you will find:

   * `inputs/` (directory)
   * `dax-generator.py`
   * `pegasusrc`
   * `submit`
   * `wordfreq`

The `inputs/` directory contains 6 public domain ebooks. The application in this example is `wordfreq`, which takes in a text file, does a word frequency analysis, and outputs a file with the frequency table. The task of the workflow is to run `wordfreq` on each book in the `inputs/` directory. A set of independent tasks like this is a common use case on OSG and this workflow can be thought of as template for such problems. For example, instead of `wordfreq` on ebooks, the application could be protein folding on a set of input structures.

When invoked, the DAX generator (`dax-generator.py`) loops over the `inputs/` directory and creates compute steps for each input. As the `wordfreq` application only has simple inputs/outputs, and no job dependencies, the DAX generator is very simple. See the `dax-generator.py` file below:

```python
#!/usr/bin/env python
from Pegasus.DAX3 import *
import sys
import os
 
base_dir = os.getcwd()
 
# Create a abstract dag
dax = ADAG("wordfreq-workflow")
 
# notifcations on state changes for the dax
dax.invoke("all", "/usr/share/pegasus/notification/email")
 
# Add executables to the DAX-level replica catalog
wordfreq = Executable(name="wordfreq", arch="x86_64", installed=False)
wordfreq.addPFN(PFN("file://" + base_dir + "/wordfreq", "local"))
dax.addExecutable(wordfreq)
 
# add jobs, one for each input file
inputs_dir = base_dir + "/inputs"
for in_name in os.listdir(inputs_dir):
 
    # Add input file to the DAX-level replica catalog
    in_file = File(in_name)
    in_file.addPFN(PFN("file://" + inputs_dir + "/" + in_name, "local"))
    dax.addFile(in_file)
 
    # Add job
    wordfreq_job = Job(name="wordfreq")
    out_file = File(in_name + ".out")
    wordfreq_job.addArguments(in_file, out_file)
    wordfreq_job.uses(in_file, link=Link.INPUT)
    wordfreq_job.uses(out_file, link=Link.OUTPUT)
    dax.addJob(wordfreq_job)
 
# Write the DAX to stdout
f = open("dax.xml", "w")
dax.writeXML(f)
f.close()
```
Note how the DAX is devoid of data movement and job details. These are added by Pegasus when the DAX is planned to an executable workflow, and provides the higher level abstraction mentioned earlier.

In the tarball there is also a `submit` script. This is a convenience script written in bash, and it performs three steps: runs the DAX generator, generates a [site catalog](http://pegasus.isi.edu/wms/docs/latest/creating_workflows.php#site), and plans/submits the workflow for execution. The site catalog does not really have to be created every time we plan/submit a workflow, but in this case we have a workflow which is used by different users, so changing the paths to scratch and output filesystems on the fly makes the workflow easier to share. See the `submit` file below:
```bash
#!/bin/bash
 
set -e
 
TOPDIR=`pwd`
 
# generate the dax
export PYTHONPATH=`pegasus-config --python`
./dax-generator.py
 
# create the site catalog
cat >sites.xml <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<sitecatalog xmlns="http://pegasus.isi.edu/schema/sitecatalog"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             xsi:schemaLocation="http://pegasus.isi.edu/schema/sitecatalog
             http://pegasus.isi.edu/schema/sc-3.0.xsd" version="3.0">
    <site  handle="local" arch="x86_64" os="LINUX">
        <head-fs>
            <scratch>
                <shared>
                    <file-server protocol="file" url="file://" mount-point="/home/$USER/data/scratch"/>
                    <internal-mount-point mount-point="/home/$USER/data/scratch"/>
                </shared>
            </scratch>
            <storage>
                <shared>
                    <file-server protocol="file" url="file://" mount-point="/home/$USER/data/outputs"/>
                    <internal-mount-point mount-point="/home/$USER/data/outputs"/>
                </shared>
            </storage>                                                                                                                          
        </head-fs>                                                                                                                              
    </site>                                                                                                                                     
    <site  handle="condorpool" arch="x86_64" os="LINUX">                                                                                        
        <head-fs>                                                                                                                               
            <scratch />                                                                                                                         
            <storage />                                                                                                                         
        </head-fs>
        <profile namespace="pegasus" key="style" >condor</profile>
        <profile namespace="condor" key="universe" >vanilla</profile>
    </site>
</sitecatalog>
EOF
 
# plan and submit the  workflow
pegasus-plan \
    --conf pegasusrc \
    --sites condorpool \
    --dir /home/$USER/data/workflows \
    --output-site local \
    --dax dax.xml \
    --submit
```
 
**Exercise 2:** Submit the workflow by executing the submit command.
```
$ ./submit
```
Note that when Pegasus plans/submits a workflow, a work directory is created and presented in the output. This directory is the handle to the workflow instance and used by Pegasus command line tools. Some useful tools to know about:

   * **_pegasus-status -v [wfdir]_**
        Provides status on a currently running workflow. ([more](http://pegasus.isi.edu/wms/docs/latest/cli-pegasus-status.php))
   * **_pegasus-analyzer [wfdir]_**
        Provides debugging clues why a workflow failed. Run this after a workflow has failed. ([more](http://pegasus.isi.edu/wms/docs/latest/cli-pegasus-analyzer.php))
   * **_pegasus-statistics [wfdir]_**
        Provides statistics, such as walltimes, on a workflow after it has completed. ([more](http://pegasus.isi.edu/wms/docs/latest/cli-pegasus-statistics.php))
   * **_pegasus-remove [wfdir]_**
        Removes a workflow from the system. ([more](http://pegasus.isi.edu/wms/docs/latest/cli-pegasus-remove.php))

During the workflow planning, Pegasus transforms the workflow to make it work well in the target execution environment. Our DAX had 6 independent tasks defined.

The executable workflow has a set of additional tasks added by Pegasus: create scratch dir, data staging in and out, and data cleanup jobs.

**Exercise 3:** Check the status of the workflow:
```
$ pegasus-status [wfdir]
```
You can keep checking the status periodically to see that the workflow is making progress.

**Exercise 4:** Examine a submit file and the `*.dag.dagman.out` files. Do these look familiar to you from previous modules in the book? Pegasus is based on HTCondor and DAGMan.
```
$ cd [wfdir]
$ cat wordfreq_ID0000001.sub
...
$ cat *.dag.dagman.out
...
```

**Exercise 5:** Keep checking progress with `pegasus-status`. Once the workflow is done, display statistics with `pegasus-statistics`:
```
$ pegasus-status [wfdir]
$ pegasus-statistics [wfdir]
...
```
 

**Exercise 6:** `cd` to the output directory and look at the outputs. Which is the most common word used in the 6 books? Hint:
```
$ cd ~/data/outputs/
$ head -n 3 *.out
```
 

**Exercise 7:** Want to try something larger? Copy the additional 994 ebooks from the many-more-inputs/ directory to the inputs/ directory:
```
$ cp many-more-inputs/* inputs/
```
As these tasks are really short, let's tell Pegasus to cluster multiple tasks together into jobs. If you do not do this step, the jobs will still run, but not very efficiently. This is because every job has a small scheduling overhead. For short jobs, the overhead is obvious. If we make the jobs longer, the scheduling overhead becomes negligible. To enable the clustering feature, edit the `dax-generator.py` script. Find the line reading:
```
wordfreq.addProfile(Profile(Namespace.PEGASUS, "clusters.size", 1))
```
Change that line to:
```
wordfreq.addProfile(Profile(Namespace.PEGASUS, "clusters.size", 50))
```
This informs Pegasus that it is ok to cluster up to 50 of the wordfreq tasks in each job. Save the file, and submit the workflow:
```
$ ./submit
```
Use `pegasus-status` and `pegasus-statistics` to monitor your workflow. Using `pegasus-statistics`, determine how many jobs ended up in your workflow.

 
**Exercise 8:** Cleanup. If you still have jobs in the queue, but want to move to the next tutorial in the book, you can remove all **your** jobs from the system with:
```
$ condor_rm -all
```

## Getting Help
For assistance or questions, please email the OSG User Support team  at `user-support@opensciencegrid.org` or visit the [help desk and community forums](http://support.opensciencegrid.org).
