#!/usr/bin/env python

from __future__ import print_function

import os
import difflib
import string
import random
import sys
from bond_dialog import OptionDialog

try:
    # Import bond safely
    from bond import spy_point
except ImportError:
    spy_point = lambda **kw: lambda f: f


"""
Reconcile the reference observations with the current ones
"""

BOLD_CHAR = '\033[1m'
RESET_CHAR = '\033[0m'

class ReconcileTool:
    """
    Base class for reconcile tools
    """

    TMP_FILE_BASE_NAME = '/tmp/bond_tmp_'

    @staticmethod
    def select(reconcile_tool=None):

        if reconcile_tool == 'accept':
            return ReconcileToolAccept()

        if reconcile_tool == 'abort':
            return ReconcileToolAbort()

        if reconcile_tool == 'console':
            return ReconcileToolConsole()

        if reconcile_tool == 'dialog':
            return ReconcileToolDialog()

        if reconcile_tool == 'kdiff3':
            return ReconcileToolKdiff3()

        if reconcile_tool is None:
            # Look at the environment variable BOND_RECONCILE
            reconcile_tool = os.environ.get('BOND_RECONCILE', 'console')
            if reconcile_tool is not None:
                return ReconcileTool.select(reconcile_tool)

        assert False, 'Unrecognized bond_reconcile tool name: {}'.format(reconcile_tool)


    @staticmethod
    @spy_point(enabled_for_groups='bond_self_test',
               require_agent_result=True)
    def _invoke_command(cmd):
        """
        Invoke a shell command. Return the exit code.
        :param cmd:
        :return:
        """
        return os.system(cmd)

    @staticmethod
    def _get_user_input_console(before_prompt, after_prompt, content, options, single_char_options):
        """
        Get input from the user using a console.
        :param prompt: The main prompt string to display to the user.
        :param options: A tuple of options to present to the user for them to select; must have
                        at least one. The last option is the default.
        :param single_char_options: A tuple of the single-character versions of each of the
                                    options supplied; this tuple must be the same length as ``options``,
                                    and each single-character version must appear within the option itself.
        :return: The user response, which is guaranteed to be one of the supplied ``options`` (if the user
                 input an invalid response the default option is used).
        """
        opts_with_single_char = \
            [string.replace(opt, char, '[' + char + ']', 1) for opt, char in zip(options, single_char_options)]
        # Default option, highlight it in bold
        opts_with_single_char[-1] = BOLD_CHAR + opts_with_single_char[-1] + RESET_CHAR
        if before_prompt != '' and after_prompt == '':
            # If there's only one, use the after, since that is when user input is grabbed
            after_prompt = before_prompt
            before_prompt = ''
        if before_prompt != '':
            print(BOLD_CHAR + before_prompt + RESET_CHAR)
        if content != '':
            print(content)
        response = raw_input(BOLD_CHAR + after_prompt + RESET_CHAR + ' (' + ' | '.join(opts_with_single_char) + '): ')
        if len(response) == 0:  # No input; return the default
            return options[-1]
        elif len(response) == 1:  # Single-character; find matching option
            return next((opt for opt, char in zip(options, single_char_options) if char == response), options[-1])
        else:
            # Make sure response is a valid option; if not return the default
            return next((opt for opt in options if opt == response), options[-1])

    @staticmethod
    def _get_user_input_dialog(before_prompt, after_prompt, content, options):
        """
        Get input from the user using a dialog box.
        :param prompt: The main prompt string to display to the user.
        :param options: A tuple of options to present to the user for them to select; must have
                        at least one. The last option is the default.
        :return: The user response, which is guaranteed to be one of the supplied ``options``
                 (if the user input an invalid response the default option is used).
        """
        return OptionDialog.create_dialog_get_value(before_prompt, after_prompt, content, options)

    @staticmethod
    @spy_point(enabled_for_groups='bond_self_test',
               require_agent_result=True,
               excluded_keys=('extra_dialog_prompt','single_char_options'),
               spy_result=True)
    def _get_user_input(before_prompt, after_prompt, content, options, single_char_options):
        """
        Acquire input from the user. Defaults to using the console to ask for input. If
        a console is not available, falls back to using a popup dialog window.
        :param prompt: The main prompt string to display to the user.
        :param options: A tuple of options to present to the user for them to select; must have
                        at least one. The last option is the default.
        :param single_char_options: A tuple of the single-character versions of each of the
                                    options supplied; this tuple must be the same length as ``options``,
                                    and each single-character version must appear within the option itself.
        :param extra_dialog_prompt: An extra message to display before the prompt only if the fallback
                                    dialog box is used.
        :return: The user response, which is guaranteed to be one of the supplied ``options`` (if the user
                 input an invalid response the default option is used).
        """
        if sys.stdin.isatty():  # We use the console to retrieve input
            return ReconcileTool._get_user_input_console(before_prompt, after_prompt,
                                                         content, options, single_char_options)
        else:  # We use a dialog box to retrieve input
            print('System console not found; using a dialog box to retrieve input instead.')
            return ReconcileTool._get_user_input_dialog(before_prompt, after_prompt, content, options)

    @staticmethod
    @spy_point(enabled_for_groups='bond_self_test')
    def _print(what):
        """
        A function to do the printing, so we can spy on it
        :param what:
        :return:
        """
        print(what)

    @staticmethod
    @spy_point(enabled_for_groups='bond_self_test', mock_only=True)
    def _random_string():
        """
        Generate a short random string
        """
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))

    @staticmethod
    def _tmp_file_name(flavor):
        """
        The name of the temporary file to use with a flavor-specific
        (e.g. diff, curr, ref) ending.
        """
        # We include a short random string to avoid potential collisions
        return ReconcileTool.TMP_FILE_BASE_NAME + ReconcileTool._random_string() + "." + flavor

    @staticmethod
    @spy_point(enabled_for_groups='bond_self_test')
    def _compute_diff(reference_lines, current_lines):
        return list(difflib.unified_diff(reference_lines, current_lines, 'reference', 'current'))

    def __init__(self):
        pass

    def reconcile(self,
                  test_name,
                  reference_file,
                  current_lines,
                  no_save=None):
        """
        Reconcile the differences
        @param test_name: the name of the test (for messages)
        @param reference_file: the name of the reference observation file
        @param current_lines: a list of the lines which make up the current set of observations
        :param no_save: if present, then disallows saving a new reference file.
               This parameter should be a string explaining why saving is disallowed.
        """

        if os.path.isfile(reference_file):
            with open(reference_file, 'r') as f:
                reference_lines = f.readlines()
        else:
            # if we do not have the reference file, pretend we have an empty one
            ReconcileTool._print('WARNING: No reference observation file found for {}: {}'.format(test_name, reference_file))
            reference_lines = list()

        # Compute a quick difference
        unified_diff = self._compute_diff(reference_lines, current_lines)

        if len(unified_diff) == 0:
            # There are no differences
            return True

        # There are differences
        merged_lines = self.invoke_tool(test_name,
                                        reference_lines,
                                        current_lines,
                                        unified_diff,
                                        no_save=no_save)
        if merged_lines is not None:
            # Accepted differences
            if no_save:
                ReconcileTool._print("Not saving reference observation file for {}: {}".format(test_name,
                                                                                               no_save))
            else:
                ReconcileTool._print('Saving updated reference observation file for {}'.format(test_name))
                if os.path.isfile(reference_file):
                    os.unlink(reference_file)
                with open(reference_file, 'w') as f:
                    f.writelines(merged_lines)
            return True
        else:
            return False

    def get_diff(self, unified_diff):
        """
        Return a message showing the diff, or a message saying there were no differences.
        """
        if len(unified_diff) > 0:
            return ''.join(unified_diff)
        else:
            return 'No differences in observations.'

    def invoke_tool(self, test_name,
                    reference_lines,
                    current_lines,
                    unified_diff,
                    no_save=None):
        """
        Invoke the actual tool
        @param
        @return either False, for a failed merge, or a list of the new lines to use as the reference
        """
        assert False, 'Must override'


class ReconcileToolAbort(ReconcileTool):
    """
    Abort all merges
    """

    def invoke_tool(self,
                    test_name,
                    reference_lines,
                    current_lines,
                    unified_diff,
                    no_save=None):
        if not no_save:
            ReconcileTool._print('{}Differences in observations for {}:{}'.format(BOLD_CHAR, test_name, RESET_CHAR))
            ReconcileTool._print(self.get_diff(unified_diff))
        ReconcileTool._print('{}Aborting (reconcile=abort) due to differences for {}{}'
                             .format(BOLD_CHAR, test_name, RESET_CHAR))
        return None


class ReconcileToolAccept(ReconcileTool):
    """
    Accept all changes
    """

    def invoke_tool(self,
                    test_name,
                    reference_lines,
                    current_lines,
                    unified_diff,
                    no_save=None):
        if no_save:
            ReconcileTool._print('{}Test {} exited with failures; observations before failure:{}'
                                 .format(BOLD_CHAR, test_name, RESET_CHAR))
            ReconcileTool._print(''.join(self.get_diff(unified_diff)))
        else:
            ReconcileTool._print('{}Differences for {}:{}'.format(BOLD_CHAR, test_name, RESET_CHAR))
            ReconcileTool._print(self.get_diff(unified_diff))
            ReconcileTool._print('{}Accepting (reconcile=accept) differences for {}{}'
                                 .format(BOLD_CHAR, test_name, RESET_CHAR))
        return current_lines


class ReconcileToolConsole(ReconcileTool):
    """
    Uses diff and console prompts to accept the changes. Falls back to a dialog window
    if no console is available for input.
    """

    def invoke_tool(self,
                    test_name,
                    reference_lines,
                    current_lines,
                    unified_diff,
                    no_save=None):

        response = 'observations' if no_save else 'diff'
        error_after_prompt = 'Saving not available due to errors in the test'.format(test_name)
        while True:
            if response == 'observations':
                if no_save:
                    after_prompt = error_after_prompt
                    options = ('kdiff3', 'diff', 'errors', 'continue')
                    single_char_opts = ('k', 'd', 'e', 'c')
                else:
                    after_prompt = 'Save new set of observations with these differences for {}?'.format(test_name)
                    options = ('kdiff3', 'diff', 'yes', 'no')
                    single_char_opts = ('k', 'd', 'y', 'n')
                before_prompt = 'Observations are shown for {}:'.format(test_name)
                response = self._input(before_prompt, after_prompt, ''.join(current_lines),
                                       options, single_char_opts)
            elif response == 'diff':
                before_prompt = 'Differences in observations are shown for {}:'.format(test_name)
                if no_save:
                    after_prompt = error_after_prompt
                    options = ('kdiff3', 'observations', 'errors', 'continue')
                    single_char_opts = ('k', 'o', 'e', 'c')
                else:
                    after_prompt = 'Save new set of observations with these differences for {}?'.format(test_name)
                    options = ('kdiff3', 'observations', 'yes', 'no')
                    single_char_opts = ('k', 'o', 'y', 'n')
                response = self._input(before_prompt, after_prompt, self.get_diff(unified_diff),
                                       options, single_char_opts)
            elif response == 'errors':
                before_prompt = 'Errors are shown for {}:'.format(test_name)
                response = self._input(before_prompt, error_after_prompt, no_save,
                                       ('kdiff3', 'observations', 'diff', 'continue'), ('k', 'o', 'd', 'c'))
            elif response == 'kdiff3':
                return ReconcileToolKdiff3().invoke_tool(test_name, reference_lines, current_lines, unified_diff,
                                                         no_save=no_save)
            elif response == 'yes':
                ReconcileTool._print('{}Accepting differences for {}{}'.format(BOLD_CHAR, test_name, RESET_CHAR))
                return current_lines
            elif response == 'no':
                ReconcileTool._print('{}Rejecting differences for {}{}'.format(BOLD_CHAR, test_name, RESET_CHAR))
                return None
            elif response == 'continue':
                return None
            else:
                assert False, 'Unknown input received!'  # Should never be reached

    def _input(self, before_prompt, after_prompt, content, options, single_char_options):
        return ReconcileTool._get_user_input(before_prompt, after_prompt, content, options, single_char_options)


class ReconcileToolDialog(ReconcileToolConsole):
    """
    Merge with a dialog window.
    """
    def _input(self, before_prompt, after_prompt, content, options, single_char_options):
        return ReconcileTool._get_user_input_dialog(before_prompt, after_prompt, content, options)


class ReconcileToolKdiff3(ReconcileTool):
    """
    Merge with kdiff3
    """

    def invoke_tool(self,
                    test_name,
                    reference_lines,
                    current_lines,
                    unified_diff,
                    no_save=None):

        # Save the current lines out to a temporary file to use with kdiff3
        current_file = self._tmp_file_name('curr')
        reference_file = self._tmp_file_name('ref')
        try:
            with open(current_file, 'w') as f:
                f.writelines(current_lines)
            with open(reference_file, 'w') as f:
                f.writelines(reference_lines)

            merged_file = None
            if no_save:
                response = ReconcileTool._get_user_input(
                    'Encountered failures while running test {}:'.format(test_name),
                    'Still want to start kdiff3?', no_save,
                    ('yes', 'no'), ('y', 'n'))
                if response != 'yes':
                    return None

                cmd = ('kdiff3 "{reference_file}" --L1 "{test_name}_REFERENCE" '
                       '"{current_file}" --L2 "{test_name}_CURRENT" ').format(
                    reference_file=reference_file,
                    current_file=current_file,
                    test_name=test_name)
                ReconcileTool._invoke_command(cmd)
                return None

            else:
                merged_file = self._tmp_file_name('merged')
                cmd = ('kdiff3 -m "{reference_file}" --L1 "{test_name}_REFERENCE" '
                       '"{current_file}" --L2 "{test_name}_CURRENT" '
                       ' -o "{merged_file}"').format(reference_file=reference_file,
                                                     current_file=current_file,
                                                     merged_file=merged_file,
                                                     test_name=test_name)

                code = ReconcileTool._invoke_command(cmd)
                if code == 0:
                    # Merged ok
                    with open(merged_file, 'r') as f:
                        merged_lines = f.readlines()
                    message = 'Merge successful; saving a new reference file. '
                    ret = merged_lines
                else:
                    message = 'Merge unsuccessful; not saving a new reference file. '
                    ret = None

                ReconcileTool._get_user_input(message, '', '', ('continue',), ('c',))
                return ret
        finally:
            if os.path.isfile(current_file):
                os.unlink(current_file)
            if os.path.isfile(reference_file):
                os.unlink(reference_file)
            if merged_file is not None and os.path.isfile(merged_file):
                os.unlink(merged_file)


def reconcile_observations(settings,
                           test_name,
                           reference_file,
                           current_lines,
                           no_save=None):
    """
    Reconcile the observations
    :param settings: a settings object
    :param reference_file: the reference file
    :param current_lines: a list of all of the lines in the current set of observations
    :param no_save: If present, then saving of new references is not allowed. This parameter
            should be a short string explaining why saving is not allowed.
    :return:
    """

    reconcile_tool = ReconcileTool.select(settings.get('reconcile'))
    return reconcile_tool.reconcile(test_name,
                                    reference_file,
                                    current_lines,
                                    no_save=no_save)


if __name__ == '__main__':
    import optparse

    optParser = optparse.OptionParser(usage=os.path.basename(__file__),
                                      description='Compare and reconciles differences in Bond observation files')

    optParser.add_option('--reconcile', dest='reconcile', action='store', default=None,
                         help='The reconcile tool to use. Available: accept, abort, console, dialog, kdiff3.')
    optParser.add_option('--reference', dest='reference', action='store', default=None,
                         help='The reference observation file')
    optParser.add_option('--current', dest='current', action='store', default=None,
                         help='The current observation file')
    optParser.add_option('--test', dest='test', action='store', default=None,
                         help='The name of the test (for UI). Default is to extract from --current')
    optParser.add_option('--no-save', dest='no_save', action='store', default=None,
                         help='If given, the reason why saving of new references is not allowed')
    (opts, args) = optParser.parse_args()
    if opts.reference is None:
        sys.exit(1)

    if opts.current is None or not os.path.isfile(opts.current):
        print('The current file does not exist: {}'.format(opts.current), file=sys.stderr)
        sys.exit(1)

    with open(opts.current, 'r') as f:
        current_lines = f.readlines()
    os.unlink(opts.current)

    # Guess the test name from the current file
    if opts.test:
        main_test_name = opts.test
    else:
        main_test_name = os.path.splitext(os.path.basename(opts.current))[0]

    if opts.reconcile:
        main_reconcile = opts.reconcile
    else:
        main_reconcile = os.environ.get('BOND_RECONCILE', 'console')

    main_settings = dict(reconcile=main_reconcile)

    if reconcile_observations(main_settings,
                              main_test_name,
                              opts.reference,
                              current_lines,
                              no_save=opts.no_save):
        sys.exit(0)
    else:
        sys.exit(1)
