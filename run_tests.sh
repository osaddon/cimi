#!/bin/sh

pylint -d W0511,I0011,E1101,E0611,F0401 -i y --report no cimi/*.py

# Make sure the test.conf is in /etc/swift!!

nosetests --with-coverage --cover-html --cover-erase --cover-package=cimi

pep8 --repeat --statistics --count cimi

pyflakes cimi

echo '\n Pychecker report \n****************************************\n'

pychecker -# 99 cimi/*.py cimi/cimiapp/*.py

