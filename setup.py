import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()
setuptools.setup(
    name="forma",
    version="0.1.0",
    author="Lena Kanellou",
    author_email="kanellou@ics.forth.gr",
    description="A python package to profiling MPI RMA operations, designed to process execution traces produced by SST Dumpi.",
    url="https://github.com/CARV-ICS-FORTH/foRMA/",
    packages=setuptools.find_namespace_packages(where='src'),
    # packages=['forma'],
    package_dir={"": "src"},
    entry_points={'console_scripts': ['forma = forma.forma:main']},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD-3-Clause",
        "Operating System :: OS Independent",
    ],
    package_data={'forma': ['schemas/epochstats.avsc', 'schemas/summary.avsc']},
	include_package_data=True,
    install_requires=[
        #"argparse",
        #"sys",
        #"glob",
        #"os",
        # "fnmatch",
        "numpy",
        #"logging",
        "pydumpi",
	"tabulate",
	"avro",
	#"contextlib",
	"pympler",
	#"ctypes",
    ],
    python_requires=">=3",
)
