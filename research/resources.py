"""Measured local process RSS and CUDA allocator peaks; never remote memory."""
import sys
import threading
import time
import psutil


class ResourceProbe:
    def __enter__(self):
        self.process=psutil.Process()
        self.baseline=self.process.memory_info().rss
        self.peak=self.baseline
        self.stop=threading.Event()
        torch=sys.modules.get('torch')
        if torch is not None and torch.cuda.is_initialized():
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        self.started=time.perf_counter()
        def sample():
            while not self.stop.wait(.02):
                self.peak=max(self.peak,self.process.memory_info().rss)
        self.thread=threading.Thread(target=sample,daemon=True)
        self.thread.start()
        return self

    def __exit__(self,*exc):
        torch=sys.modules.get('torch')
        cuda=torch is not None and torch.cuda.is_initialized()
        if cuda:
            torch.cuda.synchronize()
        self.elapsed_ms=(time.perf_counter()-self.started)*1000
        self.stop.set();self.thread.join()
        self.peak=max(self.peak,self.process.memory_info().rss)
        self.result={'elapsed_ms':self.elapsed_ms,'rss_baseline_bytes':self.baseline,'rss_peak_sampled_bytes':self.peak,
                     'rss_increase_bytes':max(0,self.peak-self.baseline),'rss_sampling_interval_ms':20,
                     'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated() if cuda else None,
                     'cuda_peak_reserved_bytes':torch.cuda.max_memory_reserved() if cuda else None,
                     'scope':'local process only; RSS sampling may miss brief peaks; CUDA is allocator memory, not remote provider VRAM'}


def resource_summary(runs):
    values=[run.get('metadata',{}).get('resources',{}) for run in runs]
    return {key:max((v[key] for v in values if v.get(key) is not None),default=None)
            for key in ('rss_peak_sampled_bytes','rss_increase_bytes','cuda_peak_allocated_bytes','cuda_peak_reserved_bytes')}
