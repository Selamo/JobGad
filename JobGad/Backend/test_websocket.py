import asyncio
import websockets
import json

async def test():
    # Replace with your actual token from login
    token = "YOUR_ACCESS_TOKEN_HERE"
    # Replace with an actual session_id from POST /coaching/sessions
    session_id = "YOUR_SESSION_ID_HERE"

    uri = f"ws://localhost:8000/api/v1/coaching/sessions/{session_id}/ws?token={token}"

    async with websockets.connect(uri) as ws:
        print("Connected!")

        # Listen for messages
        async def receive():
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print(f"\n[{data['type']}]:", json.dumps(data['data'], indent=2))

                # Auto respond to questions
                if data['type'] == 'question':
                    q_num = data['data']['question_number']
                    print(f"\nType your answer for Q{q_num}: ", end="")
                    answer = input()
                    await ws.send(json.dumps({
                        "type": "text_answer",
                        "data": {
                            "question_number": q_num,
                            "answer": answer,
                            "time_taken_seconds": 45,
                        }
                    }))

                elif data['type'] == 'session_complete':
                    print("\nSession complete! Final IRI:", data['data']['iri_score'])
                    break

        await receive()

asyncio.run(test())