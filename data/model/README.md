# Model Weights Directory

Direktori ini digunakan untuk menyimpan bobot model IndoBERT yang telah dilatih dan dioptimasi.

## File yang Dibutuhkan:
1. `optimal_thresholds_final.json` (Sudah ada di dalam repo)
2. `best_model_indobert.pt` (File bobot model PyTorch ~498 MB)

> **Catatan:** File `.pt` memiliki ukuran ~498 MB sehingga diabaikan oleh Git (`.gitignore`) karena batasan maksimal file GitHub adalah 100 MB.
> 
> Unduh file `best_model_indobert_optimized.pt` atau `best_model_indobert.pt` dari checkpoint pelatihan Google Colab Anda dan letakkan di dalam folder ini (`data/model/`).
