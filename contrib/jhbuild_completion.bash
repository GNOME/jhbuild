#!/bin/bash
#
# jhbuild tab completion for bash.
# (c) 2004, Davyd Madeley <davyd@ucc.asn.au>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2, or (at your option)
#   any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, see <http://www.gnu.org/licenses/>.
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
	local cur prev command_list i v

	cur=${COMP_WORDS[COMP_CWORD]}
	prev=${COMP_WORDS[COMP_CWORD-1]}

	case "$prev" in
	gui|tinderbox|shell|sanitycheck|bootstrap)
		command_list=""
		;;
	update|updateone|build|buildone|list|dot|info|-t|-s|-a|-n|-c)
		# FIXME: some of these options can take multiple module names
		# give them a list of modules
		command_list="$(jhbuild list -a)"
		;;
	run)
		# give them a list of commands
		COMP_WORDS=("${COMP_WORDS[0]}" "$cur")
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
		command_list="gui update updateone build buildone tinderbox run shell sanitycheck bootstrap list dot info"

		v=false
		if [ "$COMP_CWORD" -gt 2 ]; then
			for i in $command_list; do
				if [ "${COMP_WORDS[COMP_CWORD-2]}" == "$i" ]; then
					v=true
					break
				fi
			done
		fi
		
		if "$v"; then
		   	command_list=""
		fi
		;;
	esac
	
	for i in $command_list; do
		if [ -z "${i/$cur*}" ]; then
			COMPREPLY=( "${COMPREPLY[@]}" "$i" )
		fi
	done
}

# load the completion
complete -F _jhbuild jhbuild
