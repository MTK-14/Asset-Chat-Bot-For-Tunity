# session.py
#
# This file gives the chatbot a short "memory" of what was just discussed,
# so a user can ask a follow-up like "what is its status?" instead of
# retyping the asset's EPC every time.
#
# The important privacy rule: OpenAI must NEVER see a real EPC, Asset No,
# or Display ID. So instead of remembering "AST-001", we hand the model a
# safe little reference tag like "@1" or "@last". Only OUR code (this
# Session object, living only on our own machine) knows what "@1" really
# points to. When the model sends "@1" back to us in a later tool call, we
# swap it for the real identifier right before we touch the database.


class Session:
    """Keeps track of the current conversation for ONE chat session.

    Two things are stored here:
      1. history       -- the last few user/assistant turns, replayed to
                           OpenAI so it remembers what was just discussed.
                           The assistant side of history only ever contains
                           safe stub text (e.g. {"found": 1, "refs": ["@1"]}),
                           never real asset data.
      2. last_assets    -- the REAL identifiers (Asset_No values) found by
                           the most recent tool call. This list never gets
                           sent to OpenAI -- it only lives here in Python,
                           on our side.
    """

    # Keep the last 6 user+assistant exchanges (6 turns = 12 messages).
    MAX_TURNS = 6

    def __init__(self):
        self.history: list[dict] = []
        self.last_assets: list[str] = []

    def remember_assets(self, identifiers: list[str]) -> None:
        """Save the real Asset_No values from the latest tool result.

        Called after every tool call that actually found asset(s), so
        "@last" / "@1" / "@2" always point at what was just looked up.
        """
        self.last_assets = list(identifiers)

    def resolve(self, identifier: str) -> str:
        """Turn a reference like "@last" or "@2" into the real identifier.

        This is called on every "identifier" argument right before we pass
        it to a database function. If the text isn't a reference (it's a
        normal code like "AST-001" or a description like "office chair"),
        it's returned unchanged.
        """
        if not isinstance(identifier, str):
            return identifier

        ref = identifier.strip().lower()

        if ref == "@last":
            if self.last_assets:
                return self.last_assets[-1]
            return identifier  # nothing remembered yet -- let the normal lookup fail naturally

        if ref.startswith("@") and ref[1:].isdigit():
            # "@1" means the first asset we showed, "@2" the second, etc.
            index = int(ref[1:]) - 1
            if 0 <= index < len(self.last_assets):
                return self.last_assets[index]
            return identifier

        return identifier

    def add_turn(self, question: str, assistant_content_for_openai: str) -> None:
        """Record one exchange in the history OpenAI will see next turn.

        `assistant_content_for_openai` must already be safe to send to
        OpenAI -- either the model's own plain-text reply (no tool call
        happened), or a small stub dict/string like {"found": 1, "refs":
        ["@1"]}. Never pass the locally-formatted answer that contains
        real EPCs/Asset Nos here.
        """
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": assistant_content_for_openai})

        max_messages = self.MAX_TURNS * 2
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]

    def messages_for_openai(self) -> list[dict]:
        """The trimmed history to slot in between the system prompt and the
        new question when building the next OpenAI call."""
        return list(self.history)