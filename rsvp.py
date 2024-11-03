import asyncio
from even_glasses import GlassesProtocol
from even_glasses import RSVPConfig




glasses = GlassesProtocol()
config = RSVPConfig(
    words_per_group=5,  # Show 5 words at a time
    wpm=900,  # 900 words per minute
    padding_char="----->",
    retry_delay=0.01,  # Retry after 0.01 seconds
    max_retries=2,  # Retry 3 times
)

async def main():
    await glasses.scan_and_connect(timeout=10)
    await asyncio.sleep(10)
    
    
    while True:
        text = """
        Fast reading apps that display text word by word or in small groups (like two words at a time) are utilizing a technique known as Rapid Serial Visual Presentation (RSVP). Here’s what this means and why it’s used:

What is RSVP?

RSVP is a method where text is presented sequentially in the same spot on the screen, one word or a small cluster of words at a time, rather than in traditional sentence or paragraph formats. This approach is designed to streamline the reading process.

Why Use Word-by-Word or Two-Word Display?

	1.	Minimizes Eye Movement:
	•	Traditional Reading: Involves frequent eye movements (saccades) as your eyes jump from one word to the next and scan across lines.
	•	RSVP Method: Eliminates the need for these movements by keeping the focus point stationary, reducing the time spent shifting gaze.
	2.	Enhances Focus and Reduces Distractions:
	•	Presenting one or two words at a time helps concentrate the reader’s attention on each word without the distraction of surrounding text.
	3.	Increases Reading Speed:
	•	By controlling the pace at which words appear, these apps can gradually increase the speed, training your brain to process information more quickly.
	4.	Improves Comprehension and Retention:
	•	For some users, especially those practicing speed reading techniques, this method can help improve comprehension by forcing the brain to focus intently on each word or pair of words.
	5.	Efficient Use of Time:
	•	Ideal for people looking"""
        await glasses.send_rsvp(text, config)
        await asyncio.sleep(15)
    
    # await glasses.graceful_shutdown()

if __name__ == "__main__":
    asyncio.run(main())