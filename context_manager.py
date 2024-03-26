class ContextManager:
    """Allows to get adjacent lines of a certain line.
    Useful when reading a text file line by line when the lines after the desired line are not yet known."""

    class ContextReference:
        def __init__(self, context, lines_to_add):
            self.context = context
            self.lines_to_add = lines_to_add

    def __init__(self, context_lines_count):
        previous_lines_context_size = context_lines_count // 2 + 1  # +1 to include current line.
        self.following_lines_context_size = max(context_lines_count - previous_lines_context_size, 0)

        self.previous_lines = [None] * previous_lines_context_size  # lines cache
        self.current_cache_line_index = 0

        self.context_refs = []

    def update(self, line):
        self.previous_lines[self.current_cache_line_index] = line
        self.current_cache_line_index = (self.current_cache_line_index + 1) % len(self.previous_lines)

        # for multi line context: append lines that follow line with timecode found previously.
        if len(self.context_refs) > 0:
            for ref in self.context_refs:
                ref.context.append(line.strip())
                ref.lines_to_add = ref.lines_to_add - 1

            # remove refs to contexts that were filled.
            self.context_refs = [r for r in self.context_refs if r.lines_to_add > 0]

    def context_from_previous_text(self):
        line_cache_size = len(self.previous_lines)
        current_cache_line_index = self.current_cache_line_index - 1  # offset to point to current line

        context = []
        for i in range(line_cache_size):
            # iterate through cached lines in cycled buffer from oldest to newest.
            line_index = (current_cache_line_index - (line_cache_size - 1) + i) % line_cache_size
            if line := self.previous_lines[line_index]:
                context.append(line.strip())

        # save reference for adding following lines that are unknown at this moment.
        following_lines_context_size = self.following_lines_context_size
        if following_lines_context_size > 0:
            self.context_refs.append(self.ContextReference(context, following_lines_context_size))

        return context

    def is_context_completion_pending(self):
        return len(self.context_refs) > 0
