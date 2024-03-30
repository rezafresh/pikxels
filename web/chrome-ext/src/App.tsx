import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [url, setUrl] = useState<string>()
  const [trees, setTrees] = useState<any[]>()

  useEffect(() => {
    chrome.tabs.query({active: true}).then(tabs => setUrl(tabs[0].url))
  }, [])

  useEffect(() => {
    if (!url?.startsWith("https://play.pixels.xyz/pixels/share"))
      return

    const landNumber = url.split("/").slice(-1)[0]
    fetch(`https://9c4a-186-237-149-29.ngrok-free.app/land/${landNumber}/trees/`)
      .then(response => response.json())
      .then(setTrees)
  }, [url])

  return <div>
    <h2>Pixel Monitor Extension</h2>
    <span>{new Date().toLocaleString()}</span>
    {trees && JSON.stringify(trees)}
  </div>
}

export default App
