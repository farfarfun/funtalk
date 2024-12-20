class BaseASR:
    def __init__(self, *args, **kwargs):
        pass

    def load(self, *args, **kwargs):
        raise NotImplementedError

    def transcribe(self, audio, *args, **kwargs):
        raise NotImplementedError
