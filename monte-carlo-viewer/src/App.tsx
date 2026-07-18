import './App.css'
import { InputExcel } from './components/inputExcel'
import InputManual from './components/inputManual'
import { ResultsDisplay } from './components/resultDisplay'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto py-10 px-4 space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-blue-700">APLIKASI 
            SISTEM INFORMASI PREDIKSI
            CURAH HUJAN STOKASTIK
            BERBASIS KOMPUTASI MONTE CARLO
            DAN ALGORITMA BOOTSTRAPPING PYTHON
          </h1>
          <p className="text-gray-600 mt-2">
            Created By: M. Yusef Tiansyah,
            F. Heru Widodo,
            S. Bahri,
            S. Tikno,
            Tukiyat,
            Muktiyono
          </p>
          <p className="text-gray-500">
            KR. TMC PRLSDA ORKM BRIN.
          </p>
        </div>

        <div className="space-y-8">
          <InputManual />
          <InputExcel />
        </div>

        <hr className="my-8" />
        <ResultsDisplay/>
      </div>
    </div>
  )
}

export default App