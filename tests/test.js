async function getLandState(landNumber) {
    const response = await fetch(`http://localhost:9000/landstate/${landNumber}`)
    return [landNumber, response.status]
}


async function main() {
    const results = await Promise.all(
        // Array.from({length: 100}, (_, i) => i + 1).map( _ => getLandState(_))
        [667,667,667,667,667,667,].map( _ => getLandState(_))
    )
    console.log(results)
}

main()