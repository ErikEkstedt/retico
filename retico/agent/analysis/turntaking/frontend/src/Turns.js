import React, { Component, useState } from "react";
import Plot from 'react-plotly.js';

import {Button, Collapse, Container, Row, Col, Table} from 'react-bootstrap';

import Audio from './Audio';
import './turn.css';


const turnsURL = "/api/turns";
const turnAudioURL = "/api/turn_audio";


function Feature(props) {
  let tableItems = [];
  Object.entries(props.turn).forEach(([key, value]) => {
    if (key !== "eot_on_rank" && key !== "tokens_on_rank"){
      tableItems.push(
        <tr key={key} style={{textAlign: 'left'}}>
          <td> {key} </td>
          <td> {value.toString()} </td>
        </tr>
      )
    } 
  });

  return (
    <Row>
      <Table striped bordered hover size="sm" style={{width: '100%'}}>
        <thead>
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
    </Row>
  );
}


function Turn(props) {
  const [open, setOpen] = useState(false);
  let collapseId = "turn-collapse-" + props.idx;

  let trp = null
  if (props.turn.eot_on_rank !== undefined) {
    trp = (
      <Container >
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
      <Container fluid className="Turns">
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
