/* install-check
 * Copyright (C) 2002 Manish Singh
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>

static void
compare (const char *f1,
	 const char *f2)
{
  struct stat b1, b2;
  int status;
  pid_t pid, rpid;

  if (stat (f2, &b2) || stat (f1, &b1))
    return;

  if (b1.st_size != b2.st_size)
    return;

  pid = fork ();

  if (pid == 0)
    execlp ("cmp", "cmp", "-s", f1, f2, NULL);
  else if (pid < 0)
    return;
  
  do
    rpid = waitpid (pid, &status, 0);
  while (rpid == -1 && errno == EINTR);

  if (rpid != pid)
    status = -1;

  if (status != -1 && WIFEXITED (status) && WEXITSTATUS (status) == 0)
    exit (0);
}

int
main (int    argc,
      char **argv)
{
  struct stat buf;
  char **args;
  int i, len;
  char *dot, *lastarg, *start;

  lastarg = argv[argc - 1];

  dot = strrchr (lastarg, '.');
  if (dot == NULL)
    {
      len = strlen (lastarg);
      if (len < strlen ("orbit-idl-2"))
	goto install;

      start = lastarg + len - strlen ("orbit-idl-2");
      if (strcmp (start, "orbit-idl-2") != 0)
	goto install;
    }
  else if (dot[1] != 'h' && dot[1] != 'c' && strcmp (dot + 1, "idl") != 0)
    goto install;

  if ((argc == 4) &&
      (strcmp (argv[1], "-c") == 0) &&
      (strcmp (argv[2], "-d") != 0) &&
      !stat (argv[3], &buf) &&
      !S_ISDIR (buf.st_mode))
    compare (argv[2], argv[3]);
  else if ((argc == 3) &&
	   (strcmp (argv[1], "-d") != 0) &&
	   !stat (argv[2], &buf) &&
	   !S_ISDIR (buf.st_mode))
    compare (argv[1], argv[2]);
  else if ((argc == 6) &&
	   (strcmp (argv[1], "-c") == 0) &&
	   (strcmp (argv[2], "-m") == 0) &&
	   !stat (argv[5], &buf) &&
	   !S_ISDIR (buf.st_mode))
    compare (argv[4], argv[5]);
  else if ((argc == 5) &&
	   (strcmp (argv[1], "-m") == 0) &&
	   !stat (argv[4], &buf) &&
	   !S_ISDIR (buf.st_mode))
    compare (argv[3], argv[4]);

install:
  args = malloc (sizeof (char *) * (argc + 1));

  args[0] = "/usr/bin/install";

  for (i = 1; i < argc; i++)
    args[i] = argv[i];

  args[argc] = NULL;

  return execv (args[0], args);
}
