#!/bin/bash
#
# jhbuild tab completion for bash.
# (c) 2004, Davyd Madeley <davyd@ucc.asn.au>
#
# To use this completion function simply source this file into your bashrc
# with:
#	. ~/path/to/jhbuild/contrib/jhbuild_completion.bash
# This completion function depends on helper functions from the main set of
# bash completions, ensure you've sourced /etc/bash_completion before sourcing
# this file.
#

_jhbuild()
{
	local cur prev command_list i

	cur=${COMP_WORDS[COMP_CWORD]}
	prev=${COMP_WORDS[COMP_CWORD-1]}

	case "$prev" in
	gui|tinderbox|shell|sanitycheck|bootstrap)
		command_list=()
		;;
	update|updateone|build|buildone|list|dot|info|-t|-s)
		# give them a list of modules
		command_list=(`jhbuild list`)
		;;
	run)
		# give them a list of commands
		COMP_WORDS=(COMP_WORDS[0] $cur)
		COMP_CWORD=1
		_command
		;;
	-f|-m)
		# give them file completion
		_filedir
		;;
	-o)
		# give them directory completion
		_filedir -d
		;;
	*)
		command_list=(gui update updateone build buildone tinderbox run shell sanitycheck bootstrap list dot info)

		i=false
		if [ $COMP_CWORD -gt 2 ]; then
			for i in ${command_list[@]}; do
				if [ "${COMP_WORDS[COMP_CWORD-2]}" == "$i" ]; then
					i=true
					break
				fi
			done
		fi
		
		if $i; then
		   	command_list=()
		fi
		;;
	esac
	
	for i in ${command_list[@]}; do
		if [ -z "${i/$cur*}" ]; then
			COMPREPLY=( ${COMPREPLY[@]} $i )
		fi
	done
}

# load the completion
complete -F _jhbuild jhbuild
