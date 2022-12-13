import getopt
import sys

# Store input and output file names
infile = ''
outfile = ''
searchExp = ''
replaceExp = ''

# Read command line args
myopts, args = getopt.getopt(sys.argv[1:], "i:o:s:r:")

###############################
# o == option
# a == argument passed to the o
###############################
for o, a in myopts:
    if o == '-i':
        infile = a
    elif o == '-o':
        outfile = a
    elif o == '-r':
        replaceExp = a
    elif o == '-s':
        searchExp = a
    else:
        print(f"Usage: {sys.argv[0]} -i input -o output")

with open(infile, 'r') as f1:
    f2 = open(outfile, 'w')
    for line in f1:
        f2.write(line.replace(searchExp, replaceExp))
f2.close()
