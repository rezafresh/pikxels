import { useEffect, useState } from 'react'
import './App.css'

type TreesProps = {
  is_blocked: boolean
  trees: Array<{
    entity: string
    position: { x: number, y: number }
    next_respawn: string
    next_respawn_h: string
    current_state: string
  }>
}

function Trees(props: TreesProps) {
  return <>
    <div>{ props.is_blocked ? "Land Bloqueada" : "Land Liberada" }</div>
    { !props.trees ? "Nenhuma Arvore detectada" : <div>
      <table>
        <thead>
          <tr>
            <td>Entidade</td>
            <td>Posição</td>
            <td>Estagio Atual</td>
            <td>Nasce Em</td>
          </tr>
        </thead>
        <tbody>
          { props.trees.map(t => {
            return <tr>
              <td>{t.entity}</td>
              <td>X {t.position.x} Y {t.position.y}</td>
              <td>{t.current_state}</td>
              <td>{t.next_respawn_h} ({t.next_respawn})</td>
            </tr>
          })}
        </tbody>
      </table>
    </div>}
  </>
}

function App() {
  const [url, setUrl] = useState<string>()
  const [landNumber, setLandNumber] = useState<number>()
  const [trees, setTrees] = useState<TreesProps>()

  useEffect(() => {
    chrome.tabs.query({active: true}).then(tabs => setUrl(tabs[0].url))
  }, [])

  useEffect(() => {
    if (!url?.startsWith("https://play.pixels.xyz/pixels/share"))
      return

    setLandNumber(parseInt(url.split("/").slice(-1)[0]))
  }, [url])

  useEffect(() => {
    if (!landNumber)
      return

    fetch(`${import.meta.env.VITE_API_ROOT}/land/${landNumber}/trees/`)
      .then(response => response.json())
      .then(setTrees)
  }, [landNumber])

  return <div>
    <h3>Pixel Monitor Extension</h3>
    { landNumber && <h4>{"Land =>"} {landNumber}</h4> }
    { trees ? <Trees {...trees} /> : "Carregando os dados ..." }
  </div>
}

export default App
