#!/usr/bin/env python
# coding=utf-8
import datetime
from glob import glob
import os
import re


class Tester:
    """
    Test all the text files to ensure:
        * Posts are all in order - within each file the most recent should
          be first.
        * All posts are <= 280 characters in length.
        * All posts start with something that's not a lowercase character.
        * All posts end with something that's not a lowercase character.

    Outputs a report listing all errors.
    """

    def __init__(self):

        self.project_root = os.path.abspath(os.path.dirname(__file__))

        # Will be a list of dicts:
        self.errors = []

        self.post_count = 0

    def start(self):

        # Cycle through every directory in /posts/ whose name is four digits:
        for d in glob("{}/posts/{}".format(self.project_root, "[0-9]" * 4)):
            for f in os.listdir(d):
                # Test every .txt file:
                if f.endswith(".txt"):
                    self.test_file(os.path.join(self.project_root, "posts", d, f))

        last_file = None

        # Output all errors, if any.
        if len(self.errors) > 0:
            for err in self.errors:
                # err has 'filepath', 'time' and 'text' elements.
                if last_file is None or last_file != err["filepath"]:
                    # eg 'FILE: 1660/01.txt'
                    dir_file = "/".join(err["filepath"].split("/")[-2:])
                    print("\nFILE posts/{}".format(dir_file))

                print(" {}: {}".format(err["time"], err["text"]))

                last_file = err["filepath"]

        print("\n{:,} posts checked.".format(self.post_count))

        if len(self.errors) == 0:
            print("\nEverything is OK.")

    def test_file(self, filepath):
        "Test an individual file."

        with open(filepath) as file:
            lines = [line for line in file]

        prev_time = None

        for line in lines:
            if line != "":
                # Use same match as in poster.py, and only test matching lines.

                pattern = r"""
                    ^                           # Start of line
                    (
                        \d\d\d\d-\d\d-\d\d      # Date like 1666-02-09
                        \s
                        \d\d\:\d\d              # Time like 14:08
                    )                           # GROUP 1: Date and time
                    (?:                         # Don't count this group
                        \s                      # A space before the 'r'
                        (
                            \w                  # A literal 'r' (probably).
                        )                       # GROUP 2: r (or None)
                    )?                          # The 'r ' is optional
                    \s+                         # One or more spaces
                    (.*?)                       # The post text
                    $                           # End of line
                """

                line_match = re.search(pattern, line, re.VERBOSE)

                if line_match:
                    [post_time, post_kind, post_text] = line_match.groups()

                    self.post_count += 1

                    # Check times are in the correct order.

                    try:
                        t = datetime.datetime.strptime(post_time, "%Y-%m-%d %H:%M")
                    except ValueError as e:
                        self.add_error(filepath, post_time, e)
                        # Have to return as we won't have a valid value for t.
                        return

                    if prev_time is not None:
                        if t > prev_time:
                            self.add_error(
                                filepath,
                                post_time,
                                "Time is after previous time ({}).".format(prev_time),
                            )
                        elif t == prev_time:
                            self.add_error(
                                filepath,
                                post_time,
                                "Time is the same as previous time ({}).".format(
                                    prev_time
                                ),
                            )
                    prev_time = t

                    # Test valid kinds

                    if post_kind is not None:
                        if post_kind != "r":
                            self.add_error(
                                filepath,
                                post_time,
                                "Kind should be nothing or 'r'. It was: '{}'.".format(
                                    post_kind
                                ),
                            )

                    # Test post length.

                    if len(post_text) > 280:
                        self.add_error(
                            filepath,
                            post_time,
                            "Post is {} characters long.".format(len(post_text)),
                        )

                    # Test first/last characters.

                    if post_text[0].islower():
                        self.add_error(
                            filepath,
                            post_time,
                            'Post begins with lowercase character ("{}...")'.format(
                                post_text[:20]
                            ),
                        )

                    if post_text[-1].islower():
                        self.add_error(
                            filepath,
                            post_time,
                            'Post ends with lowercase character, not punctuation ("...{}")'.format(
                                post_text[-20:]
                            ),
                        )

                    if post_text.endswith(" "):
                        self.add_error(
                            filepath,
                            post_time,
                            'Post ends with a space ("...{}")'.format(post_text[-20:]),
                        )

                    # Catch any footnote numbers left in, like "at a limner1 that he"
                    post_match = re.search(r"([^\s^\d^,^\(+]\d+)", post_text)
                    if post_match:
                        span = post_match.span()
                        start = span[0] - 10
                        end = span[1] + 10
                        self.add_error(
                            filepath,
                            post_time,
                            'Post contains footnote ("{}")'.format(
                                post_text[start:end]
                            ),
                        )

                    # Tests for errors that I had to correct.

                    # 'jj' or 'kk' from making a mistake in vim:
                    post_match = re.search(r"\W?(jj|kk)\W?", post_text)
                    if post_match:
                        span = post_match.span()
                        start = span[0] - 10
                        end = span[1] + 10
                        self.add_error(
                            filepath,
                            post_time,
                            '"{}" found: "{}")'.format(
                                post_match.groups()[0], post_text[start:end]
                            ),
                        )

    def add_error(self, filepath, dt, txt):
        self.errors.append({"filepath": filepath, "time": dt, "text": txt})


def main():
    tester = Tester()

    tester.start()


if __name__ == "__main__":
    main()
