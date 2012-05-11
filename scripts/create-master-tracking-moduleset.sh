#! /bin/sh

VERSION=$(grep '^moduleset =' jhbuild/defaults.jhbuildrc | awk -F"-"  '{ print $NF }' | sed -e "s/'//g")

for FILENAME in modulesets/*-$VERSION.modules
do
    TRUNK_FILENAME=$(echo $FILENAME | sed -e "s/$VERSION/trunk/")
    xsltproc --nodtdattr scripts/create-master-tracking-moduleset.xsl \
        $FILENAME > $TRUNK_FILENAME
    sed -i -e "s/-$VERSION.modules/-trunk.modules/" $TRUNK_FILENAME
done

