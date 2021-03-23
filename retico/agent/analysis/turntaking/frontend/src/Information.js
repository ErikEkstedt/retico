import {Container, Row, Col, Card, Button } from 'react-bootstrap';
import polyEncoderImg from './assets/poly_encoder.png';

const elizaURL = "https://dl.acm.org/doi/10.1145/365153.365168";
const blenderURL = "https://arxiv.org/pdf/2004.13637.pdf"


export default function Information() {
	const cardStyle = {width: '18rem'};
	const containerStyle = {textAling: 'center'};
  return (
    <Container fluid style={containerStyle}>

			<Row className='justify-content-center'>
				<h1> Information </h1>
			</Row >

			<Row>
				<Col>
					<Card style={cardStyle}>
						<Card.Body>
							<Card.Img variant="top" src={polyEncoderImg} maxWidth='200px'/>
							<Card.Title>Blender</Card.Title>
							<Card.Text>
								Recipes for building an open-domain chatbot
							</Card.Text>
							<Button variant="primary" href={blenderURL}> Paper </Button>
						</Card.Body>
					</Card>
				</Col>
			</Row>

			<Row sm={4}>
				<Col>
					<Card style={cardStyle}>
						<Card.Body>
							<Card.Title>Chat with LM</Card.Title>
							<Card.Text>
								Generate responses during the conversation.
							</Card.Text>
						</Card.Body>
					</Card>
				</Col>

		
				<Col>
					<Card style={cardStyle}>
						<Card.Body>
							<Card.Title>RepeatBot</Card.Title>
							<Card.Text>
								<p>
									A bot which repeats the user utterance. Repeats user words in TTS or plays back the recorded user audio.
								</p>	
								<p>Slinky conversation. A conversation where each utterance is duplicated and the user plays both interlocutors. Training then omits the redundant turns. learn EOT, TFO prior a response and turn sequences. </p>
							</Card.Text>
						</Card.Body>
					</Card>
				</Col>
				<Col>
					<Card style={cardStyle}>
						<Card.Body>
							<Card.Title>Yes/No Bot</Card.Title>
							<Card.Text>
								The agent only answers yes or no using varying turn-taking approaches. The fastest possible answer (time lower bound on average yes time) and a delayed answer, no average relative yes average time, for no answers.
							</Card.Text>
						</Card.Body>
					</Card>
				</Col>

				<Col>
					<Card style={cardStyle}>
						<Card.Body>
							<Card.Title>ELIZABot</Card.Title>
							<Card.Text>
								One of the first ever automatic chatbot systems.
								ELIZA: A Computer Program For the Study of Natural Language Communication BetweenMan and Machine, 1966
							</Card.Text>
							<Button variant="primary" href={elizaURL}> Paper </Button>
						</Card.Body>
					</Card>
				</Col>


			</Row>

    </Container>
  );
}
