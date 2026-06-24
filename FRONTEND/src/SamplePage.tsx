import './SamplePage.css'

export default function SamplePage() {
  return (
    <div className="sample-container">
      <div className="sample-header">
        <h1 className="sample-title">Tailwind CSS Sample Page</h1>
        <p className="sample-subtitle">Testing Tailwind styling with separate CSS files</p>
      </div>

      <div className="sample-grid">
        <div className="sample-card">
          <h2 className="sample-card-title">Card One</h2>
          <p className="sample-card-text">
            This card uses Tailwind classes defined in the CSS file. The styling is working correctly!
          </p>
          <button className="sample-button">Learn More</button>
        </div>

        <div className="sample-card">
          <h2 className="sample-card-title">Card Two</h2>
          <p className="sample-card-text">
            Responsive design works with Tailwind breakpoints (md, lg, xl).
          </p>
          <span className="sample-badge">New</span>
        </div>

        <div className="sample-card">
          <h2 className="sample-card-title">Card Three</h2>
          <p className="sample-card-text">
            Hover effects and transitions are applied smoothly across all elements.
          </p>
          <button className="sample-button">View Details</button>
        </div>
      </div>

      <div className="mt-12 max-w-7xl mx-auto">
        <div className="sample-alert">
          <div className="sample-alert-title">✓ Tailwind CSS is Working!</div>
          <div className="sample-alert-text">
            All Tailwind utilities and custom component classes are being applied correctly through separate CSS files.
          </div>
        </div>
      </div>

      <div className="mt-12 max-w-7xl mx-auto">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Color Palette Test</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-red-500 text-white p-4 rounded text-center font-semibold">Red</div>
          <div className="bg-blue-500 text-white p-4 rounded text-center font-semibold">Blue</div>
          <div className="bg-green-500 text-white p-4 rounded text-center font-semibold">Green</div>
          <div className="bg-purple-500 text-white p-4 rounded text-center font-semibold">Purple</div>
          <div className="bg-pink-500 text-white p-4 rounded text-center font-semibold">Pink</div>
          <div className="bg-yellow-500 text-white p-4 rounded text-center font-semibold">Yellow</div>
          <div className="bg-indigo-500 text-white p-4 rounded text-center font-semibold">Indigo</div>
          <div className="bg-cyan-500 text-white p-4 rounded text-center font-semibold">Cyan</div>
        </div>
      </div>
    </div>
  )
}
