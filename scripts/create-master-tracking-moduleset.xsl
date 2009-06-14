<?xml version='1.0'?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

  <xsl:template match="branch[not(@repo) and not(@module) and @revision]">
    <branch />
  </xsl:template>

  <xsl:template match="include[@href = 'gnome-suites-2.26.modules']">
    <include href="gnome-suites-trunk.modules"/>
  </xsl:template>

  <xsl:template match="node()|@*">
    <xsl:copy>
      <xsl:apply-templates select="node()|@*"/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
