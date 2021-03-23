import React, { Component, useState } from "react";
import Plot from 'react-plotly.js';

import {Button, Collapse, Container, Row, Col, Table} from 'react-bootstrap';

import Audio from './Audio';
import './turn.css';


const turnsURL = "/api/turns";
const turnAudioURL = "/api/turn_audio";


function TrpGuesses(guess) {
  const [open, setOpen] = useState(false);

  let predictions = [];
	if (guess === undefined) {
		guess.predictions = [{null: ""}];
		guess.utteranxe = "";
	} 

  Object.entries(guess.predictions).forEach((entry, key) => {
    predictions.push(<li key={key}> {entry[1]} </li>)
  });

  let color = '#c57c7c';
  if (guess.trp > .3) {
    color = '#add8e6'
  }

  return (
    <li style={{textAlign: 'left'}} key={guess.time}>
      <Button
        onClick={() => setOpen(!open)}
        aria-controls="example-collapse-text"
        aria-expanded={open}
        style={{background: color, color: 'black'}}
      >
        {guess.utterance}
      </Button>
      <Collapse in={open}>
        <div id="example-collapse-text" style={{color: 'white', background: '#404040'}}>
          <ul> {predictions} </ul>
        </div>
      </Collapse>
    </li>
  );
}


function Feature(props) {
  let tableItems = [];
  tableItems.push(
    <tr key={'start_time'} style={{textAlign: 'left'}}>
      <td> start_time </td>
      <td> {props.turn.start_time.toString()} </td>
    </tr>
  )
  tableItems.push(
    <tr key={'end_time'} style={{textAlign: 'left'}}>
      <td> end_time </td>
      <td> {props.turn.end_time.toString()} </td>
    </tr>
  )

  Object.entries(props.turn).forEach(([key, value]) => {
    if (key !== "eot_on_rank" && key !== "tokens_on_rank" && key !== 'end_time' && key !== 'start_time' && key !== 'all_trps'){
      tableItems.push(
        <tr key={key} style={{textAlign: 'left'}}>
          <td> {key} </td>
          <td> {value.toString()} </td>
        </tr>
      )
    } 
  });

  let trpItems = [];
  if (props.turn.all_trps !== undefined) {
    Object.entries(props.turn.all_trps).forEach(([key, value]) => {
      trpItems.push(TrpGuesses(value))
    })
  }

  return (
    <Row>
      <Table striped bordered size="sm" style={{width: '100%', color: '#eaeaea', background: '#404040'}}>
        <thead style={{textAlign: 'left'}}>
          <tr>
            <th>data</th>
            <th>value</th>
          </tr>
        </thead>
        <tbody>
          {tableItems}
        </tbody>
      </Table>
      <hr/>
      <ul>
        {trpItems}
      </ul>
    </Row>
  );
}


function Turn(props) {
  const [open, setOpen] = useState(false);
  let collapseId = "turn-collapse-" + props.idx;

  let trp = null
  if (props.turn.eot_on_rank !== undefined) {
    trp = (
      <Container fluid style={{textAlign: 'center'}}>
        <Plot
          data={[{type: 'bar', x: props.turn.tokens_on_rank, y: props.turn.eot_on_rank}]}
          layout={{title: 'TRP', yaxis: {range: [0, 1]}, xaxis: {tickangle: -45}}}
        />
      </Container >
    );
  }

  let side='right';
  let marginLeft='30px';
  let marginRight='0px';
  if (props.turn.name === 'agent') {
    side='left'
    marginLeft='0px';
    marginRight='30px';
  }
  return (
    <li 
       className="Turn" 
      key={'turn_' + props.idx} 
      style={{marginLeft: marginLeft, marginRight: marginRight, textAlign: side}}
    >
      <Button 
        onClick={() => setOpen(!open)}
        aria-controls={collapseId} 
        aria-expanded={open}
        id={"turn-"+props.turn.name}
        style={{minWidth: '55%', textAlign: side}}
        // style={{textAlign: side}}
      >
        {props.turn.utterance}
      </Button>
      <Collapse in={open} transition={null}>
        <Container id={collapseId} styles={{'padding': "10px"}}>
          {/* <Audio */} 
          {/*   audioURL={turnAudioURL+ "/" + props.idx} */}
          {/*   id={"turn-audio-" + props.idx} */}
          {/*   progressColor='#aa5555' */}
          {/*   waveColor='red' */}
          {/* /> */}
          <Feature turn={props.turn}/>
          {trp}
        </Container>
      </Collapse>
    </li>
  );
}


class Turns extends Component {
  constructor(props) {
    super(props);
    this.state = {
      turns: null,
      audioURL: "turn_audio_" + props.turn_index,
    }
  }

  componentDidMount() {
    if (this.props.interaction !== "") {
      fetch(turnsURL+"/"+this.props.interaction).then(response => response.json()).then((data) => {
        this.setState({turns: data.turns})
      })
    }
  }

  getTurns() {
    if (this.state.turns === null){
      return
    }
    let listItems = [];
    for (let i in this.state.turns) {
      listItems.push(
        <Turn 
          turn={this.state.turns[i]}
          idx={i}
          key={'turn-'+i}
        />
      )
    }
    return listItems;
  }

  render() {
    let listItems = this.getTurns();
    return (
      <Container fluid className="Turns" style={{margin: '10px 0px'}}>
        <Row>
          <Col md={{offset: 1}}> <h3 style={{color: 'green'}}>Agent</h3> </Col>
          <Col md={{offset: 7}}> <h3 style={{color: 'blue'}}>User</h3> </Col>
        </Row>
        <ol style={{listStyleType: 'none'}}>
          {listItems}
        </ol>
      </Container>
    );
  }
}

export default Turns;
