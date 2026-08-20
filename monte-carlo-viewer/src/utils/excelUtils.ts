// utils/excelUtils.ts
export async function downloadSimulationExcel() {
    const baseurl = import.meta.env.VITE_BACKEND_URL as string
    const res = await fetch(`${baseurl}/export-excel`)
    if (!res.ok) {
        throw new Error("Failed to export Excel")
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob)

    const a = document.createElement("a")
    a.href = url
    a.download = "simulation_results.xlsx"
    a.click()
    window.URL.revokeObjectURL(url)
}

export async function downloadDasSimulationExcel() {
    const baseUrl = import.meta.env.VITE_BACKEND_URL as string
    const res = await fetch(`${baseUrl}/export-excel-das`)

    if (!res.ok) {
        throw new Error("Error to converting the Data from CSV into Excel")
    }

    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)

    const a = document.createElement("a")
    a.href = url
    a.download = "das_simulation_results.xlsx"
    a.click()
    window.URL.revokeObjectURL(url)
}