import { invoke } from "@tauri-apps/api/tauri";
import { open } from "@tauri-apps/api/dialog";
import { DownloadFormatPreset, AppDependencies, AppConfig, GeneralConfig, PreferenceConfig } from '@/types';

// ... (Existing functions checkDependencies, openExternalLink) ...

export async function checkDependencies(): Promise<AppDependencies> {
    return await invoke("check_dependencies");
}

export async function openExternalLink(url: string): Promise<void> {
  return await invoke("open_external_link", { url });
}

export async function closeSplash(): Promise<void> {
  return await invoke("close_splash");
}

// --- Config API ---

export async function getAppConfig(): Promise<AppConfig> {
    return await invoke("get_app_config");
}

export async function saveGeneralConfig(config: GeneralConfig): Promise<void> {
    return await invoke("save_general_config", { config });
}

export async function savePreferenceConfig(config: PreferenceConfig): Promise<void> {
    return await invoke("save_preference_config", { config });
}

// --- Downloader API ---

export async function startDownload(
  url: string, 
  downloadPath: string | undefined, 
  formatPreset: DownloadFormatPreset,
  embedMetadata: boolean,
  embedThumbnail: boolean,
  filenameTemplate: string
): Promise<string> {
  return await invoke("start_download", { 
    url, 
    downloadPath, 
    formatPreset,
    embedMetadata,
    embedThumbnail,
    filenameTemplate
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