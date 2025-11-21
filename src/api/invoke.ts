// src/api/invoke.ts

import { invoke } from "@tauri-apps/api/tauri";
import { open } from "@tauri-apps/api/dialog";
import { DownloadFormatPreset } from '@/types';

export async function checkYtDlpPath(): Promise<boolean> {
  try {
    return await invoke("check_yt_dlp_path");
  } catch (error) {
    if (error === "YtDlpNotFound") {
      return false;
    }
    throw error;
  }
}

export async function openExternalLink(url: string): Promise<void> {
  return await invoke("open_external_link", { url });
}

export async function startDownload(
  url: string, 
  downloadPath: string | undefined, 
  formatPreset: DownloadFormatPreset,
  embedMetadata: boolean,
  embedThumbnail: boolean
): Promise<string> {
  return await invoke("start_download", { 
    url, 
    downloadPath, 
    formatPreset,
    embedMetadata,
    embedThumbnail
  });
}

export async function cancelDownload(jobId: string): Promise<void> {
  return await invoke("cancel_download", { jobId });
}

export async function selectDirectory(): Promise<string | null> {
    const selected = await open({
        directory: true,
        multiple: false,
    });
    
    if (Array.isArray(selected)) {
        return selected[0];
    }
    return selected;
}