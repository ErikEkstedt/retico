import React, { Component, useState } from "react";
import { Button, Collapse, Container, Row, Col, Table } from "react-bootstrap";

import Plot from "react-plotly.js";
import WaveSurfer from "wavesurfer.js";

const turnAudioURL = "/api/turn_audio";

export default class TurnAudioFeatures extends Component {
  constructor(props) {
    super(props);
    this.state = {
      playPauseButtonId: 'pause',
      color: "#fafafa",
			divId: "turn-audio-" + this.props.idx,
			audioURL: turnAudioURL+"/"+this.props.idx.toString()+"/"+this.props.startTime.toString()+'/'+this.props.endTime.toString()+"/"+this.props.interaction,
    }; 
  }

  // Waveform + AudioPlayer
  componentDidMount() {
    this.waveform = WaveSurfer.create({
      container: '#'+this.state.divId,
      backend: "MediaElement",
      mediaControls: true,
      backgroundColor: this.state.color,
      scrollParent: true,
    });
    this.waveform.load(this.state.audioURL);
  }

  render() {
    return (
      <div id={this.state.divId}></div>
    );
  }
}


function TrpGuesses(guess) {
	const [open, setOpen] = useState(false);

	if (guess.predictions === undefined) {
		return;
	}

	let color = "#c57c7c";
	if (guess.trp > 0.3) {
		color = "#4db367";
	}

	let predictions = [];
	Object.entries(guess.predictions).forEach((entry, key) => {
		predictions.push(<li key={key}> {entry[1]} </li>);
	});

	return (
		<li key={guess.time}>
			<Button
				onClick={() => setOpen(!open)}
				aria-controls="example-collapse-text"
				aria-expanded={open}
				style={{ background: color, color: "black", border: "black 1px solid"}}
			>
				{guess.utterance}
			</Button>
			<Collapse in={open}>
				<div
					id="example-collapse-text"
					style={{ color: "white", background: "#404040" }}
				>
					<ul> {predictions} </ul>
				</div>
			</Collapse>
		</li>
	);
}

function TurnInfo(props) {
	let tableItems = [];
	tableItems.push(
		<tr key={"start_time"} style={{ textAlign: "left" }}>
			<td> start_time </td>
			<td> {props.turn.start_time.toString()} </td>
		</tr>
	);
	tableItems.push(
		<tr key={"end_time"} style={{ textAlign: "left" }}>
			<td> end_time </td>
			<td> {props.turn.end_time.toString()} </td>
		</tr>
	);
	tableItems.push(
		<tr key={"utterance"} style={{ textAlign: "left" }}>
			<td> utterance </td>
			<td> {props.turn.utterance} </td>
		</tr>
	);

	if (props.turn.all_trps !== undefined){
		let idx = props.turn.all_trps.length - 1;
		let utt = props.turn.all_trps[idx].utterance;
		tableItems.push(
			<tr key={"utterance_at_eot"} style={{ textAlign: "left" }}>
				<td>utterance at eot</td>
				<td> {utt} </td>
			</tr>
		);

		let notIncluded = ""
		if ( utt !== 0){
			notIncluded = props.turn.utterance.substring(utt.length, props.turn.utterance.length);
		}
		tableItems.push(
			<tr key={"notIncluded"} style={{ textAlign: "left" }}>
				<td> string len diff on EOT </td>
				<td> {notIncluded} </td>
			</tr>
		);
	}


	const omit = [ 
		"eot_on_rank", 
		"tokens_on_rank", 
		"end_time", 
		"start_time", 
		"prel_utterance", 
		"utterance", 
		"pred_time",
		"name", 
		"all_trps",
		"utterance_at_eot"
	];



	Object.entries(props.turn).forEach(([key, value]) => {
		if (!omit.includes(key) ) {
			tableItems.push(
				<tr key={key} style={{ textAlign: "left" }}>
					<td> {key} </td>
					<td> {value.toString()} </td>
				</tr>
			);
		}
	});

	let trpItems = [];
	if (props.turn.all_trps !== undefined) {
		Object.entries(props.turn.all_trps).forEach(([key, value]) => {
			trpItems.push(TrpGuesses(value));
		});
	}

	return (
		<Row>
			<Table
				striped
				bordered
				size="sm"
				style={{ width: "100%", color: "#eaeaea", background: "#404040" }}
			>
				<thead style={{ textAlign: "left" }}>
					<tr>
						<th>data</th>
						<th>value</th>
					</tr>
				</thead>
				<tbody>{tableItems}</tbody>
			</Table>
			<hr />
			<ul>{trpItems}</ul>
		</Row>
	);
}


export function Turn(props) {
	const [open, setOpen] = useState(false);
	let collapseId = "turn-collapse-" + props.idx;

	let turnOrder = 'first';
	if (props.turn.name === "user") {
		turnOrder = 'last';
	}

	// const actionButtonStyle = {background: '#ff3e3e', border: '#8f2222 1px solid', color: 'black'};
	return (
		<Container fluid>
			<Row >
				<Col style={{padding: '0px'}} md={(8, { order: turnOrder})}> 
					<Button
						onClick={() => setOpen(!open)}
						aria-controls={collapseId}
						aria-expanded={open}
						id={"turn-" + props.turn.name}
						style={{ width: "100%", textAlign: 'left'}}
					>
						{props.turn.utterance}
					</Button>
				</Col>
				{/* <Col style={{padding: '0px', height: '100%'}} md={1} ><Button style={actionButtonStyle} block onClick={() => setOpen(!open)}>X<sub>{props.idx}</sub></Button></Col> */}
				{/* <Col style={{padding: '0px', height: '100%'}} md={1} ><Button style={actionButtonStyle} block onClick={() => setOpen(!open)}>S<sub>{props.idx}</sub></Button></Col> */}
				{/* <Col style={{padding: '0px', height: '100%'}} md={1} ><Button style={actionButtonStyle} block onClick={() => setOpen(!open)}>T<sub>{props.idx}</sub></Button></Col> */}
				{/* <Col style={{padding: '0px', height: '100%'}} md={1} ><Button style={actionButtonStyle} block onClick={() => setOpen(!open)}>C<sub>{props.idx}</sub></Button></Col> */}
			</Row>
			<Row >
				<Collapse 
					in={open} 
					transition={null}
				>
					<Container id={collapseId} styles={{ padding: "10px" }}>
						<TurnAudioFeatures idx={props.idx} startTime={props.turn.start_time} endTime={props.turn.end_time} interaction={props.interaction}/>
						<TurnInfo turn={props.turn} />
					</Container>
				</Collapse>
			</Row>
		</Container>
	);
}
