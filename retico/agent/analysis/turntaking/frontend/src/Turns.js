import React, { Component } from "react";

import { Container, Row, Col } from "react-bootstrap";

import { Turn } from "./Turn";
import "./turn.css";

const turnsURL = "/api/turns";


class Turns extends Component {
	constructor(props) {
		super(props);
		this.state = {
			turns: null,
			audioURL: "turn_audio_" + props.turn_index,
		};
	}

	componentDidMount() {
		if (this.props.interaction !== "") {
			fetch(turnsURL + "/" + this.props.interaction)
				.then((response) => response.json())
				.then((data) => {
					this.setState({ turns: data.turns });
				});
		}
	}

	getTurns() {
		if (this.state.turns === null) {
			return;
		}
		let listItems = [];
		for (let i in this.state.turns) {
			listItems.push(
				<li
					className="Turn"
					key={"turn_" + {i}}
				>
					<Turn turn={this.state.turns[i]} idx={i} key={"turn-" + i} interaction={this.props.interaction}/>
				</li>
			);
		}
		return listItems;
	}

	render() {
		let listItems = this.getTurns();
		return (
			<Container fluid className="Turns" style={{ margin: "10px 0px" }}>
				<Row>
					<Col md={{ offset: 1 }}>
						{" "}
						<h3 style={{ color: "green" }}>Agent</h3>{" "}
					</Col>
					<Col md={{ offset: 7 }}>
						{" "}
						<h3 style={{ color: "blue" }}>User</h3>{" "}
					</Col>
				</Row>
				<ol style={{ listStyleType: "none" }}>{listItems}</ol>
			</Container>
		);
	}
}

export default Turns;
