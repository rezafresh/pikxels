async function getLandState(landNumber) {
    const response = await fetch(`http://localhost:9000/land/${landNumber}/state/`)
    return [landNumber, response.status, response.status !== 200 ? await response.text() : "OK"]
}

async function main() {
    return await Promise.all(
        Array.from({length: process.argv[2]}, (_, i) => i + 1).map( _ => getLandState(_))
    )
}

main().then(console.log).catch(console.error)