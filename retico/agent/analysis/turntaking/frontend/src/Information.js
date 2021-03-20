import {Container, Card, Button } from 'react-bootstrap';
import polyEncoderImg from './assets/poly_encoder.png';

const elizaURL = "https://dl.acm.org/doi/10.1145/365153.365168";
const blenderURL = "https://arxiv.org/pdf/2004.13637.pdf"


export default function Information() {
  return (
    <Container>
      <h1> Information </h1>
      <Card >
        <Card.Body>
          <Card.Title>ELIZA: A Computer Program For the Study of Natural Language Communication BetweenMan and Machine, 1966</Card.Title>
          <Card.Text>
            One of the first ever automatic chatbot systems.
          </Card.Text>
          <Button variant="primary" href={elizaURL}> Paper </Button>
        </Card.Body>
      </Card>

      <Card >
        <Card.Body>
          <Card.Img variant="top" src={polyEncoderImg} width='200px'/>
          <Card.Title>Blender</Card.Title>
          <Card.Text>
            Recipes for building an open-domain chatbot
          </Card.Text>
          <Button variant="primary" href={blenderURL}> Paper </Button>
        </Card.Body>
      </Card>

    </Container>
  );
}
