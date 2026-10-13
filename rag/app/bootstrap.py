"""Download pinned public models and index public samples during deployment build."""
from .service import RagService
if __name__=='__main__':
    service=RagService();print('Public sample index ready:',service.samples.count(),'passages')
