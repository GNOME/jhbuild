<?xml version="1.0"?><!--*- mode: nxml -*-->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

  <xsl:template match="cvsroot">
    <repository type="cvs" name="{@name}" cvsroot="{@root}">
      <xsl:if test="@password"><xsl:copy-of select="@password" /></xsl:if>
      <xsl:if test="@default"><xsl:copy-of select="@default" /></xsl:if>
    </repository>
  </xsl:template>

  <xsl:template match="svnroot">
    <repository type="svn" name="{@name}" href="{@href}">
      <xsl:if test="@default"><xsl:copy-of select="@default" /></xsl:if>
    </repository>
  </xsl:template>

  <xsl:template match="arch-archive">
    <repository type="arch" name="{@name}" href="{@href}">
      <xsl:if test="@default"><xsl:copy-of select="@default" /></xsl:if>
    </repository>
  </xsl:template>

  <xsl:template match="cvsmodule">
    <autotools>
      <xsl:attribute name="id">
        <xsl:choose>
          <xsl:when test="@id">
            <xsl:value-of select="@id"/>
          </xsl:when>
          <xsl:when test="@checkoutdir">
            <xsl:value-of select="@id"/>
          </xsl:when>
          <xsl:otherwise>
            <xsl:value-of select="@module"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:attribute>
      <xsl:if test="@autogenargs">
	<xsl:copy-of select="@autogenargs" />
      </xsl:if>
      <xsl:if test="@makeargs">
	<xsl:copy-of select="@makeargs" />
      </xsl:if>
      <xsl:if test="@supports-non-srcdir-builds">
	<xsl:copy-of select="@supports-non-srcdir-builds" />
      </xsl:if>
      <xsl:text>&#x0a;    </xsl:text>
      <branch>
	<xsl:if test="@cvsroot">
	  <xsl:attribute name="repo">
	    <xsl:value-of select="@cvsroot"/>
	  </xsl:attribute>
	</xsl:if>
	<xsl:if test="@root">
	  <xsl:attribute name="repo">
	    <xsl:value-of select="@root"/>
	  </xsl:attribute>
	</xsl:if>
	<xsl:if test="@module"><xsl:copy-of select="@module" /></xsl:if>
	<xsl:if test="@revision"><xsl:copy-of select="@revision" /></xsl:if>
	<xsl:if test="@checkoutdir"><xsl:copy-of select="@checkoutdir" /></xsl:if>
      </branch>
      <xsl:apply-templates select="node()"/>
    </autotools>
  </xsl:template>

  <xsl:template match="svnmodule">
    <autotools id="{@id}">
      <xsl:if test="@autogenargs">
	<xsl:copy-of select="@autogenargs" />
      </xsl:if>
      <xsl:if test="@makeargs">
	<xsl:copy-of select="@makeargs" />
      </xsl:if>
      <xsl:if test="@supports-non-srcdir-builds">
	<xsl:copy-of select="@supports-non-srcdir-builds" />
      </xsl:if>
      <xsl:text>&#x0a;    </xsl:text>
      <branch>
	<xsl:if test="@root">
	  <xsl:attribute name="repo">
	    <xsl:value-of select="@root"/>
	  </xsl:attribute>
	</xsl:if>
	<xsl:if test="@module"><xsl:copy-of select="@module" /></xsl:if>
	<xsl:if test="@checkoutdir"><xsl:copy-of select="@checkoutdir" /></xsl:if>
      </branch>
      <xsl:apply-templates select="node()"/>
    </autotools>
  </xsl:template>

  <xsl:template match="archmodule">
    <autotools id="{@id}">
      <xsl:if test="@autogenargs">
	<xsl:copy-of select="@autogenargs" />
      </xsl:if>
      <xsl:if test="@makeargs">
	<xsl:copy-of select="@makeargs" />
      </xsl:if>
      <xsl:if test="@supports-non-srcdir-builds">
	<xsl:copy-of select="@supports-non-srcdir-builds" />
      </xsl:if>
      <xsl:text>&#x0a;    </xsl:text>
      <branch>
	<xsl:if test="@root">
	  <xsl:attribute name="repo">
	    <xsl:value-of select="@root"/>
	  </xsl:attribute>
	</xsl:if>
	<xsl:if test="@version">
	  <xsl:attribute name="module">
	    <xsl:value-of select="@version"/>
	  </xsl:attribute>
	</xsl:if>
	<xsl:if test="@checkoutdir"><xsl:copy-of select="@checkoutdir" /></xsl:if>
      </branch>
      <xsl:apply-templates select="node()"/>
    </autotools>
  </xsl:template>

  <xsl:template match="suggests">
    <after>
      <xsl:apply-templates select="node()"/>
    </after>
  </xsl:template>

  <xsl:template match="node()" priority="-1">
    <xsl:copy>
      <xsl:copy-of select="@*" />
      <xsl:apply-templates select="node()"/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
