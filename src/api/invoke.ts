import { invoke } from "@tauri-apps/api/tauri";

export async function checkYtDlpPath(): Promise<boolean> {
  try {
    return await invoke("check_yt_dlp_path");
  } catch (error) {
    // In Tauri, when a Rust function returning Result::Err returns an error,
    // the promise is rejected. For Rust unit enum variants serialized with serde,
    // the error is the string name of the variant.
    if (error === "YtDlpNotFound") {
      return false;
    }
    // Re-throw any other unexpected errors
    throw error;
  }
}

export async function openExternalLink(url: string): Promise<void> {
  return await invoke("open_external_link", { url });
}

export async function startDownload(url: string): Promise<string> {
  return await invoke("start_download", { url });
}

export async function cancelDownload(jobId: string): Promise<void> {
  return await invoke("cancel_download", { jobId });
}
