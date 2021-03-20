import React, { Component } from "react";
import {Container, Col, Navbar, Form, FormControl} from 'react-bootstrap';
import Plot from 'react-plotly.js';

const baseUrl = "/api/aggregate"

const Navigation = (props) => {

  return (
    <Navbar expand="sm"> 
      <Navbar.Brand >Aggregate</Navbar.Brand>
      <Form inline>
        <FormControl type="text" placeholder="Search" className="mr-sm-2" />
      </Form>
    </Navbar>
  );
}

export default class Aggregate extends Component {
  constructor(props) {
    super(props);
    this.state = { 
      stats: null,
      tfoBins: 10,
      tfoBinSize: .1,
      tfoBinEnd: 2.1,
    };
  }

  componentDidMount() {
    fetch(baseUrl+'/stats').then(response => response.json()).then((data) => {
      this.setState({stats: data})
    });
  }

  getTFO() {
    if (this.state.stats === null) {
      return
    }

    return (
      <Plot
        data={[{
          x: this.state.stats.baseline.tfo.agent.duration, 
            type: 'histogram', 
            histnorm: 'probability', 
            name: 'baseline', 
            xbins: { 
              end: this.state.tfoBinEnd,
              size: this.state.tfoBinSize,
              start: 0,
            }
        },
          {
            x: this.state.stats.baselinevad.tfo.agent.duration, 
            type: 'histogram', 
            histnorm: 'probability', 
            name: 'baselinevad', 
            xbins: { 
              end: this.state.tfoBinEnd,
              size: this.state.tfoBinSize,
              start: 0,
            }
          },
          {
            x: this.state.stats.prediction.tfo.agent.duration, 
            type: 'histogram', 
            histnorm: 'probability', 
            name: 'prediction', 
            xbins: { 
              end: this.state.tfoBinEnd,
              size: this.state.tfoBinSize,
              start: 0,
            }
          }]}
      />
    )
  }

  getGrades() {
    if (this.state.stats === null || this.state.stats === undefined) {
      return
    }

    let y = ['responsiveness', 'natural', 'enjoyment'];
    let baseline_x = [
      this.state.stats.baseline.grades.responsiveness.mean,
      this.state.stats.baseline.grades.natural.mean,
      this.state.stats.baseline.grades.enjoyment.mean,
    ]
    let baselinevad_x = [
      this.state.stats.baselinevad.grades.responsiveness.mean,
      this.state.stats.baselinevad.grades.natural.mean,
      this.state.stats.baselinevad.grades.enjoyment.mean,
    ]
    let prediction_x = [
      this.state.stats.prediction.grades.responsiveness.mean,
      this.state.stats.prediction.grades.natural.mean,
      this.state.stats.prediction.grades.enjoyment.mean,
    ]

    console.log(baseline_x)
    return (
      <Plot
        data={[
          { y: baseline_x, x: y, type: 'bar', name: 'baseline'},
          { y: baselinevad_x, x: y, type: 'bar', name: 'baselinevad'},
          { y: prediction_x, x: y, type: 'bar', name: 'prediction'},
      ]}
      />

    )
  }

  getAnnotation() {
    if (this.state.stats === null ) {
      return
    }
    console.log(this.state.stats.baseline.anno)
    console.log(this.state.stats.prediction.anno)

    let y = ['interruption', 'missed-eot'];
    let baseline_x = [
      this.state.stats.baseline.anno.interruption.mean,
      this.state.stats.baseline.anno.missed_eot.mean,
    ]
    let baselinevad_x = [
      this.state.stats.baselinevad.anno.interruption.mean,
      this.state.stats.baselinevad.anno.missed_eot.mean,
    ]
    let prediction_x = [
      this.state.stats.prediction.anno.interruption.mean,
      this.state.stats.prediction.anno.missed_eot.mean,
    ]

    console.log(baseline_x)
    return (
      <Plot
        data={[
          { y: baseline_x, x: y, type: 'bar', name: 'baseline'},
          { y: baselinevad_x, x: y, type: 'bar', name: 'baselinevad'},
          { y: prediction_x, x: y, type: 'bar', name: 'prediction'},
      ]}
      />

    )
  }


  render () {
    const tfo = this.getTFO();
    const grades = this.getGrades();
    const anno = this.getAnnotation();
    return (
      <div>
        <Navigation />
        <Container >
          <Col>
            <h3>TFO</h3>
            {tfo}
            <h3>Grades</h3>
            {grades}
            <h3>Anno</h3>
            {anno}
          </Col>
        </Container >
      </div>
    );
  }
}
